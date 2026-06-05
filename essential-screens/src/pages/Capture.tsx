import { useNavigate } from "react-router-dom";
import { Camera, Image as ImageIcon, Upload, Mic, Send, StopCircle, Volume2, Sparkles } from "lucide-react";
import React, { useRef, useState, useEffect } from "react";
import { chat, voiceChat, getChats } from "../lib/api";
import Header from "../components/Header";

const Capture = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [capturedFile, setCapturedFile] = useState<File | null>(null);
  const [cameraStatus, setCameraStatus] = useState<'idle' | 'requesting' | 'active' | 'denied' | 'error'>('idle');
  const [cameraError, setCameraError] = useState<string>('');
  const [isVideoReady, setIsVideoReady] = useState(false);
  const [activeStream, setActiveStream] = useState<MediaStream | null>(null);

  // User & Session
  const userId = localStorage.getItem("user_id") || "demo_user";

  const addNotification = (title: string, message: string, type: 'success' | 'system' = 'success') => {
    const saved = localStorage.getItem(`notifications_${userId}`);
    const notifications = saved ? JSON.parse(saved) : [];
    const newNotif = {
      id: Date.now(),
      title,
      message,
      time: "Just now",
      unread: true,
      type
    };
    const updated = [newNotif, ...notifications].slice(0, 10);
    localStorage.setItem(`notifications_${userId}`, JSON.stringify(updated));
    window.dispatchEvent(new Event("notificationsUpdated"));
  };

  // Chat & Voice States
  const [chatMessages, setChatMessages] = useState<{ role: 'user' | 'assistant', content: string }[]>([]);
  const [inputText, setInputText] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const chatEndRef = useRef<HTMLDivElement>(null);


  const handleCapture = () => {
    console.log('Capture button clicked');

    if (!videoRef.current || !canvasRef.current) {
      console.error('Video or canvas ref not available');
      alert('Camera not ready. Please try again.');
      return;
    }

    const video = videoRef.current;
    const canvas = canvasRef.current;

    console.log('Video dimensions:', video.videoWidth, 'x', video.videoHeight);

    // Check if video has valid dimensions
    if (!video.videoWidth || !video.videoHeight) {
      console.error('Video dimensions not ready');
      alert('Camera is still loading. Please wait a moment and try again.');
      return;
    }

    // Set canvas dimensions to a high-quality square for AI focus (center crop)
    const size = Math.min(video.videoWidth, video.videoHeight);
    canvas.width = size;
    canvas.height = size;

    const startX = (video.videoWidth - size) / 2;
    const startY = (video.videoHeight - size) / 2;

    // Draw the centered square from the video frame to canvas
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      console.error('Could not get canvas context');
      return;
    }

    // Pass 1: Draw the cropped frame
    ctx.drawImage(video, startX, startY, size, size, 0, 0, size, size);

    // Pass 2: Subtle "Hackathon Enhancement" (Contrast/Saturation boost)
    // This makes textures pop for the AI Vision model
    ctx.globalCompositeOperation = 'overlay';
    ctx.fillStyle = 'rgba(128,128,128,0.1)';
    ctx.fillRect(0, 0, size, size);
    ctx.globalCompositeOperation = 'source-over';

    console.log('Frame cropped and enhanced to square canvas');

    // Convert canvas to blob and then to File
    canvas.toBlob((blob) => {
      if (!blob) {
        console.error('Failed to create blob from canvas');
        alert('Failed to capture image. Please try again.');
        return;
      }

      console.log('Blob created, size:', blob.size);

      const timestamp = new Date().toISOString();
      const file = new File([blob], `camera-input-${timestamp}.jpg`, { type: 'image/jpeg' });

      // Create object URL for preview
      const imageUrl = URL.createObjectURL(blob);
      console.log('Image URL created:', imageUrl);

      setCapturedImage(imageUrl);
      setCapturedFile(file);
      setIsCameraActive(false);

      // Stop the camera stream
      if (video.srcObject) {
        const stream = video.srcObject as MediaStream;
        stream.getTracks().forEach(track => track.stop());
      }

      // Clear active stream state if it exists
      if (typeof setActiveStream === 'function') {
        setActiveStream(null);
      }

      addNotification("Photo Captured", "Photo optimized and ready for analysis.", "success");
    }, 'image/jpeg', 0.9);
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const imageUrl = URL.createObjectURL(file);
      setCapturedImage(imageUrl);
      setCapturedFile(file);
      setIsCameraActive(false);
      addNotification("Image Uploaded", "Image successfully prepared for analysis.", "success");
    }
  };

  const handleAnalyzeUpload = () => {
    if (capturedImage) {
      addNotification("Analysis Started", "We're identifying your meal now...", "system");
      navigate("/review", { state: { image: capturedImage, file: capturedFile } });
    }
  };

  // AI Chat Logic
  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const data = await getChats(userId);
        if (data && Array.isArray(data.history)) {
          setChatMessages(data.history.map((msg: any) => ({
            role: msg.role === 'user' ? 'user' : 'assistant',
            content: msg.content
          })));
        }
      } catch (err) {
        console.error("Failed to fetch chat history:", err);
      }
    };
    fetchHistory();
  }, [userId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const handleSendMessage = async () => {
    if (!inputText.trim() || isThinking) return;

    const userMsg = inputText.trim();
    setInputText("");
    setChatMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsThinking(true);

    try {
      const response = await chat(userId, userMsg);
      setChatMessages(prev => [...prev, { role: 'assistant', content: response.response }]);
    } catch (err) {
      console.error("Chat error:", err);
      setChatMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I'm having trouble connecting right now." }]);
    } finally {
      setIsThinking(false);
    }
  };

  // Voice Assistant Logic
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        const audioFile = new File([audioBlob], "voice_query.wav", { type: 'audio/wav' });

        setIsThinking(true);
        setChatMessages(prev => [...prev, { role: 'user', content: "🎤 [Voice Message]" }]);

        try {
          const response = await voiceChat(userId, audioFile);
          setChatMessages(prev => [
            ...prev.filter(m => m.content !== "🎤 [Voice Message]"),
            { role: 'user', content: `🎤 ${response.transcription}` },
            { role: 'assistant', content: response.response }
          ]);
        } catch (err) {
          console.error("Voice chat error:", err);
          setChatMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I couldn't process your voice message." }]);
        } finally {
          setIsThinking(false);
        }

        stream.getTracks().forEach(track => track.stop());
      };

      recorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error("Microphone access error:", err);
      alert("Could not access microphone.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const startCamera = async () => {
    // Check browser support
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setCameraStatus('error');
      setCameraError('Camera is not supported in this browser. Please use a modern browser like Chrome, Firefox, or Safari.');
      addNotification('Camera Not Supported', 'Your browser does not support camera access.', 'system');
      return;
    }

    try {
      // Reset states
      setCapturedImage(null);
      setCameraError('');
      setIsVideoReady(false);
      setCameraStatus('requesting');

      console.log('Requesting camera access...');

      // Request camera access with constraints
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "environment",
          width: { ideal: 1920 },
          height: { ideal: 1080 }
        }
      });

      console.log('Camera access granted, stream obtained');

      setIsCameraActive(true);
      setActiveStream(stream);
      // Video rendering is handled by useEffect when videoRef.current becomes available
    } catch (err: any) {
      console.error("Camera access error:", err);

      // Detailed error handling based on error type
      let errorMessage = 'Could not access camera.';
      let errorTitle = 'Camera Error';

      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setCameraStatus('denied');
        errorTitle = 'Permission Denied';
        errorMessage = 'Camera permission was denied. Please allow camera access in your browser settings and try again.';
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setCameraStatus('error');
        errorTitle = 'No Camera Found';
        errorMessage = 'No camera was detected on this device. Please connect a camera and try again.';
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        setCameraStatus('error');
        errorTitle = 'Camera In Use';
        errorMessage = 'Camera is being used by another application. Please close other apps using the camera and try again.';
      } else if (err.name === 'OverconstrainedError' || err.name === 'ConstraintNotSatisfiedError') {
        setCameraStatus('error');
        errorTitle = 'Camera Configuration Error';
        errorMessage = 'Camera does not support the required settings. Trying with default settings...';

        // Retry with minimal constraints
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ video: true });
          if (videoRef.current) {
            videoRef.current.srcObject = stream;
            setIsCameraActive(true);
            setCameraStatus('active');
            addNotification('Camera Active', 'Camera is ready with default settings.', 'success');
            return;
          }
        } catch (retryErr) {
          console.error('Retry failed:', retryErr);
        }
      } else if (err.name === 'TypeError') {
        setCameraStatus('error');
        errorTitle = 'Security Error';
        errorMessage = 'Camera access requires HTTPS. Please access this site via HTTPS or localhost.';
      } else {
        setCameraStatus('error');
        errorMessage = `Camera error: ${err.message || 'Unknown error occurred'}`;
      }

      setCameraError(errorMessage);
      addNotification(errorTitle, errorMessage, 'system');
    }
  };

  useEffect(() => {
    if (activeStream && videoRef.current && isCameraActive) {
      console.log('Attaching stream to video element');
      videoRef.current.srcObject = activeStream;
      setCameraStatus('active');
      addNotification('Camera Active', 'Camera is ready. Position your food and click capture.', 'success');
    }
  }, [activeStream, isCameraActive]);

  const handleVideoReady = () => {
    if (videoRef.current) {
      const width = videoRef.current.videoWidth;
      const height = videoRef.current.videoHeight;
      console.log('Video metadata loaded. Dimensions:', width, 'x', height);

      if (width > 0 && height > 0) {
        setIsVideoReady(true);
        console.log('Video is ready for capture');
      } else {
        console.warn('Video dimensions are invalid:', width, 'x', height);
      }
    }
  };

  const captureFromCamera = () => {
    // Trigger the camera input
    const cameraInput = document.getElementById('camera-input') as HTMLInputElement;
    if (cameraInput) {
      cameraInput.click();
    }
  };

  const handleCameraCapture = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const imageUrl = URL.createObjectURL(file);
      setCapturedImage(imageUrl);
      setCapturedFile(file);
      setIsCameraActive(false);
      addNotification("Photo Captured", "Photo successfully captured and ready for analysis.", "success");
    }
  };

  React.useEffect(() => {
    return () => {
      // Cleanup camera stream
      if (videoRef.current && videoRef.current.srcObject) {
        const stream = videoRef.current.srcObject as MediaStream;
        stream.getTracks().forEach(track => {
          track.stop();
          console.log('Camera track stopped:', track.kind);
        });
        videoRef.current.srcObject = null;
      }

      // Revoke object URLs to prevent memory leaks
      if (capturedImage && capturedImage.startsWith('blob:')) {
        URL.revokeObjectURL(capturedImage);
      }

      // Reset states
      setIsCameraActive(false);
      setIsVideoReady(false);
      setCameraStatus('idle');
      setActiveStream(null);
    };
  }, []);

  const retakeImage = () => {
    setCapturedImage(null);
    setIsCameraActive(false);
    if (activeStream) {
      activeStream.getTracks().forEach(track => track.stop());
      setActiveStream(null);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header />
      <canvas ref={canvasRef} style={{ display: 'none' }} />

      <main className="flex-1 px-6 py-4 flex flex-col overflow-y-auto custom-scrollbar">
        <div className="animate-slide-up mb-6" style={{ animationDelay: '0.2s' }}>
          <h1 className="text-3xl font-bold text-foreground mb-2">Log your meal</h1>
          <p className="text-muted-foreground">Instantly analyze your food nutrition using our AI engine.</p>
        </div>

        <div className="flex-1 min-h-[400px] relative rounded-3xl overflow-hidden glass-card border-none shadow-2xl animate-slide-up group" style={{ animationDelay: '0.3s' }}>
          <div className="absolute inset-0 bg-black flex items-center justify-center">
            {!isCameraActive && !capturedImage && (
              <div className="absolute inset-0 bg-[url('https://images.unsplash.com/photo-1490645935967-10de6ba17061?w=1600&q=80')] bg-cover bg-center opacity-40 transition-opacity duration-700" />
            )}
            {isCameraActive && (
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                onLoadedMetadata={handleVideoReady}
                className="w-full h-full object-cover"
              />
            )}
            {capturedImage && (
              <img src={capturedImage} alt="Captured" className="w-full h-full object-contain bg-black/50 backdrop-blur-sm" />
            )}
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent pointer-events-none" />
          </div>

          <div className="absolute inset-0 flex flex-col items-center justify-center p-8 z-10 pointer-events-none">
            {!isCameraActive && !capturedImage && (
              <div className="text-center mb-8 animate-fade-in pointer-events-auto">
                <h2 className="text-4xl font-bold text-white mb-4">Scan Your Meal</h2>
                {cameraError && (
                  <div className="mb-4 p-4 bg-destructive/20 border border-destructive/50 rounded-lg backdrop-blur-sm">
                    <p className="text-white font-semibold mb-2">Camera Error</p>
                    <p className="text-white/90 text-sm">{cameraError}</p>
                  </div>
                )}
                <div className="flex gap-4 justify-center">
                  <button
                    onClick={startCamera}
                    disabled={cameraStatus === 'requesting'}
                    className="flex items-center gap-2 bg-primary hover:bg-primary/90 text-primary-foreground px-8 py-4 rounded-full font-semibold shadow-xl glow-primary transition-all hover:scale-105 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Camera size={24} /> {cameraStatus === 'requesting' ? 'Requesting Access...' : cameraStatus === 'denied' || cameraStatus === 'error' ? 'Retry Camera' : 'Start Camera'}
                  </button>
                  <button onClick={() => fileInputRef.current?.click()} className="flex items-center gap-2 bg-white/10 hover:bg-white/20 backdrop-blur-md text-white px-8 py-4 rounded-full font-semibold border border-white/20 transition-all hover:scale-105 active:scale-95">
                    <ImageIcon size={24} /> Browse File
                  </button>
                  <input type="file" ref={fileInputRef} onChange={handleFileUpload} accept="image/*" className="hidden" />
                </div>
              </div>
            )}
            {isCameraActive && !isVideoReady && (
              <div className="pointer-events-auto absolute inset-0 flex items-center justify-center bg-black/30 backdrop-blur-sm z-40">
                <div className="text-center">
                  <div className="w-12 h-12 border-4 border-white border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
                  <p className="text-white font-semibold">Initializing camera...</p>
                  <p className="text-white/70 text-sm">Please wait</p>
                </div>
              </div>
            )}
            {isCameraActive && isVideoReady && (
              <button
                onClick={handleCapture}
                className="pointer-events-auto absolute bottom-12 left-1/2 -translate-x-1/2 transform w-24 h-24 rounded-full border-4 border-white bg-white/30 flex items-center justify-center hover:scale-110 hover:bg-white/40 active:scale-95 transition-all duration-200 z-50"
                style={{
                  boxShadow: '0 0 40px rgba(255, 255, 255, 0.8), inset 0 0 20px rgba(255, 255, 255, 0.4)',
                  backgroundColor: 'rgba(255, 255, 255, 0.3)'
                }}
              >
                <div className="w-20 h-20 rounded-full bg-white/90 animate-pulse"></div>
              </button>
            )}
            {capturedImage && (
              <div className="pointer-events-auto flex gap-4 mt-auto mb-8 animate-fade-in">
                <button onClick={retakeImage} className="bg-white/10 hover:bg-white/20 backdrop-blur-md text-white px-6 py-3 rounded-full font-semibold border border-white/20 transition-all hover:scale-105">
                  Change Image
                </button>
                <button onClick={handleAnalyzeUpload} className="flex items-center gap-2 gradient-primary text-primary-foreground px-8 py-3 rounded-full font-semibold shadow-xl glow-primary transition-all hover:scale-105">
                  <Upload size={20} /> Analyze Photo
                </button>
              </div>
            )}
          </div>
          <div className="absolute inset-8 border-2 border-white/20 rounded-2xl pointer-events-none opacity-50">
            <div className="absolute top-0 left-0 w-8 h-8 border-t-4 border-l-4 border-white/60 -mt-0.5 -ml-0.5 rounded-tl-lg"></div>
            <div className="absolute top-0 right-0 w-8 h-8 border-t-4 border-r-4 border-white/60 -mt-0.5 -mr-0.5 rounded-tr-lg"></div>
            <div className="absolute bottom-0 left-0 w-8 h-8 border-b-4 border-l-4 border-white/60 -mb-0.5 -ml-0.5 rounded-bl-lg"></div>
            <div className="absolute bottom-0 right-0 w-8 h-8 border-b-4 border-r-4 border-white/60 -mb-0.5 -mr-0.5 rounded-br-lg"></div>
          </div>
        </div>

        <div className="mt-8 animate-slide-up mb-8" style={{ animationDelay: '0.4s' }}>
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center">
              <Sparkles size={16} className="text-accent" />
            </div>
            <h3 className="text-xl font-bold text-foreground">AI Nutrichat</h3>
            <span className="bg-accent/10 border border-accent/20 text-accent text-[10px] px-2 py-0.5 rounded-full font-bold">BETA VOICE</span>
          </div>

          <div className="glass-card rounded-3xl overflow-hidden border-border/50 flex flex-col h-[400px] shadow-lg">
            <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar">
              {chatMessages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center opacity-50 space-y-2">
                  <Volume2 size={48} className="text-muted-foreground mb-2" />
                  <p className="text-foreground font-medium">How can I help you today?</p>
                  <p className="text-xs text-muted-foreground max-w-[200px]">Ask me about nutrition, recipes, or dietary advice.</p>
                </div>
              ) : (
                chatMessages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}>
                    <div className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm shadow-sm ${msg.role === 'user' ? 'bg-primary text-primary-foreground rounded-tr-none' : 'bg-secondary/80 text-foreground border border-border/50 rounded-tl-none'}`}>
                      {msg.content}
                    </div>
                  </div>
                ))
              )}
              {isThinking && (
                <div className="flex justify-start animate-fade-in">
                  <div className="bg-secondary/80 text-foreground border border-border/50 rounded-2xl rounded-tl-none px-4 py-2 text-sm flex items-center gap-2">
                    <div className="flex gap-1">
                      <div className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce" style={{ animationDelay: '0s' }}></div>
                      <div className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                      <div className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                    </div>
                    AI is thinking...
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            <div className="p-4 bg-secondary/20 border-t border-border/50 backdrop-blur-md">
              <div className="flex items-center gap-2">
                <button onClick={isRecording ? stopRecording : startRecording} className={`w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300 ${isRecording ? 'bg-destructive text-white animate-pulse' : 'bg-secondary text-foreground hover:bg-secondary/80'}`}>
                  {isRecording ? <StopCircle size={20} /> : <Mic size={20} />}
                </button>
                <input type="text" value={inputText} onChange={(e) => setInputText(e.target.value)} onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()} placeholder={isRecording ? "Listening..." : "Type your query here..."} className="flex-1 bg-background/50 border border-border/50 rounded-full px-4 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary transition-all" />
                <button onClick={handleSendMessage} disabled={!inputText.trim() || isThinking} className="w-10 h-10 rounded-full bg-primary text-primary-foreground flex items-center justify-center hover:bg-primary/90 disabled:opacity-50 transition-all shadow-glow">
                  <Send size={18} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Capture;
