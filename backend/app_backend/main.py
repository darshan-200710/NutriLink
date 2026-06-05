from fastapi import FastAPI, UploadFile, File, HTTPException
# Force reload to pick up new .env changes
from backend.app_backend.models import AnalysisResponse, NutritionInfo, ChatRequest, UserRegister, UserLogin
from backend.app_backend.integration import FitnessIntegration
from backend.app_backend.firebase_utils import db
from datetime import datetime
from firebase_admin import firestore
from backend.ai_core.gemini_client import analyze_food_image, generate_text, analyze_audio
# from ai_core.openai_client import analyze_food_image
# from ai_core.groq_client import analyze_food_image
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import bcrypt

app = FastAPI(title="Food Vision API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, you might want to specify the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    """Diagnostic endpoint for deployment debugging."""
    return {
        "status": "online",
        "database": "connected" if db else "missing_credentials",
        "ai_key": "configured" if os.getenv("GOOGLE_API_KEY") else "missing",
        "env_vars": {
            "FIREBASE_CREDENTIALS_PATH": os.getenv("FIREBASE_CREDENTIALS_PATH", "default"),
            "GOOGLE_API_KEY_PRESENT": bool(os.getenv("GOOGLE_API_KEY")),
            "BACKEND_URL_EXTERNAL": os.getenv("RENDER_EXTERNAL_URL", "not_set")
        }
    }

@app.get("/")
def read_root():
    return {"status": "online", "message": "Food Vision Backend is Running. Visit /health for diagnostics."}

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_food(file: UploadFile = File(...), user_id: str = "demo_user"):
    """
    Receives an image, processing it via AI, 
    saves to Firebase, and syncs with Fitness Platform.
    """
    print(f"\n[DEBUG] Analysis Request Received: user_id={user_id}, filename={file.filename}")
    
    # 1. Save temp file - Sanitize filename for Windows (remove colons from ISO timestamps)
    safe_filename = file.filename.replace(":", "-").replace(" ", "_")
    temp_filename = f"temp_{safe_filename}"
    print(f"[DEBUG] Saving temp file: {temp_filename}")
    with open(temp_filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    print(f"[DEBUG] Calling AI Analysis...")
    # 2. Call AI
    ai_result = analyze_food_image(temp_filename)
    print(f"[DEBUG] AI Analysis Result: {ai_result}")
    # Use Groq result if available; on error return HTTP 502
    if "error" in ai_result:
        print(f"AI Error: {ai_result.get('error')}")
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {ai_result.get('error')}")

    # Build nutrition model from AI result
    nutrition_data = ai_result
    nutrition_info = NutritionInfo(**nutrition_data)
    
    if not nutrition_info.is_food:
        final_message = "No food detected. Please try again with a clearer image of your meal."
    elif nutrition_info.confidence < 0.6:
        final_message = f"We identified this as {nutrition_info.food_name}, but the image was a bit {nutrition_info.unclear_reason or 'unclear'}. Please verify if this is correct."
    else:
        final_message = "Food analyzed successfully"

    # 3. Store in Firebase

    
    # 3. Store in Firebase
    try:
        if db:
            doc_ref = db.collection(u'food_logs').document()
            doc_ref.set({
                u'user_id': user_id,
                u'food_name': nutrition_info.food_name,
                u'calories': nutrition_info.calories,
                u'timestamp': datetime.now(),
                u'nutrition': nutrition_info.dict()
            })
            
            # Update user food memories
            try:
                from backend.memory_manager import memory_manager
                from backend.pattern_analyzer import PatternAnalyzer
                
                # Update frequency memory
                memory_manager.update_frequency_memory(
                    user_id=user_id,
                    food_name=PatternAnalyzer.normalize_food_name(nutrition_info.food_name),
                    nutrition_data={
                        'calories': nutrition_info.calories,
                        'protein_g': nutrition_info.protein_g,
                        'carbs_g': nutrition_info.carbs_g,
                        'fats_g': nutrition_info.fats_g
                    }
                )
                
                # Update timing pattern based on current time
                current_hour = datetime.now().hour
                if 5 <= current_hour < 11:
                    meal_type = "breakfast"
                elif 11 <= current_hour < 16:
                    meal_type = "lunch"
                elif 16 <= current_hour < 19:
                    meal_type = "snack"
                else:
                    meal_type = "dinner"
                
                memory_manager.update_timing_pattern(
                    user_id=user_id,
                    meal_type=meal_type,
                    food_name=PatternAnalyzer.normalize_food_name(nutrition_info.food_name),
                    time_str=datetime.now().strftime("%H:%M")
                )
                
                # Check if eating limit reached
                limit_check = memory_manager.check_eating_limit(
                    user_id=user_id,
                    food_name=PatternAnalyzer.normalize_food_name(nutrition_info.food_name)
                )
                
                if limit_check and limit_check.get("reached"):
                    # Store notification in Firebase for persistent display
                    try:
                        notif_ref = db.collection(u'notifications').document()
                        notif_ref.set({
                            u'user_id': user_id,
                            u'type': u'limit_reached',
                            u'title': u'Eating Limit Reached',
                            u'message': limit_check.get('message'),
                            u'timestamp': datetime.now(),
                            u'unread': True,
                            u'food_name': limit_check.get('food'),
                            u'count': limit_check.get('count')
                        })
                        print(f"🔔 Limit notification created for {user_id}: {limit_check.get('message')}")
                    except Exception as notif_error:
                        print(f"Warning: Could not create notification: {notif_error}")
                
                print(f"✓ Updated food memories for {user_id}")
            except Exception as mem_error:
                print(f"Warning: Could not update memories: {mem_error}")
                # Continue even if memory update fails
                
    except Exception as e:
        print(f"\n[WARNING] Database Write Failed: {e}")
        print("Continuing without saving to DB (Hackathon Mode)\n")
    
    # 4. Integrate with Fitness Platform
    sync_result = FitnessIntegration.sync_workout(
        user_id=user_id, 
        calories=nutrition_info.calories, 
        protein=nutrition_info.protein_g
    )
    
    # Clean up
    if os.path.exists(temp_filename):
        os.remove(temp_filename)
        
    return AnalysisResponse(
        nutrition=nutrition_info,
        message=final_message,
        fitness_sync_status=sync_result
    )


@app.post("/analyze_debug")
async def analyze_food_debug(file: UploadFile = File(...), user_id: str = "demo_user"):
    """Debug endpoint that returns raw AI output (no parsing) for troubleshooting."""
    safe_filename = file.filename.replace(":", "-").replace(" ", "_")
    temp_filename = f"temp_{safe_filename}"
    with open(temp_filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    ai_result = analyze_food_image(temp_filename)

    # Clean up
    if os.path.exists(temp_filename):
        os.remove(temp_filename)

    return {"ai_result": ai_result}

@app.get("/history/{user_id}")
async def get_history(user_id: str):
    """
    Fetches food history for a specific user from Firebase.
    """
    if not db:
        raise HTTPException(status_code=503, detail="Database not initialized")
        
    try:
        logs_ref = db.collection(u'food_logs')
        query = logs_ref.where(u'user_id', u'==', user_id).order_by(u'timestamp', direction=firestore.Query.DESCENDING).limit(10)
        docs = query.stream()
        
        history = []
        for doc in docs:
            log_data = doc.to_dict()
            # Convert datetime to string for JSON serialization
            if 'timestamp' in log_data and log_data['timestamp']:
                log_data['timestamp'] = log_data['timestamp'].isoformat()
            history.append(log_data)
            
        return {"user_id": user_id, "history": history}
    except Exception as e:
        print(f"Error fetching history: {e}")
        # Fallback if index is not created yet (Firestore requires indexes for where + order_by)
        try:
            docs = logs_ref.where(u'user_id', u'==', user_id).limit(10).stream()
            history = []
            for doc in docs:
                log_data = doc.to_dict()
                if 'timestamp' in log_data and log_data['timestamp']:
                    log_data['timestamp'] = log_data['timestamp'].isoformat()
                history.append(log_data)
            return {"user_id": user_id, "history": history, "note": "Simple query used (no ordering)"}
        except:
            raise HTTPException(status_code=500, detail=f"Failed to fetch history: {str(e)}")

@app.get("/coach/{user_id}")
async def get_coaching(user_id: str):
    """
    Analyzes user history and provides coaching insights and meal suggestions.
    """
    if not db:
        raise HTTPException(status_code=503, detail="Database not initialized")
        
    try:
        # 1. Fetch recent history
        logs_ref = db.collection(u'food_logs')
        docs = logs_ref.where(u'user_id', u'==', user_id).order_by(u'timestamp', direction=firestore.Query.DESCENDING).limit(10).stream()
        
        history_summary = []
        total_calories = 0
        for doc in docs:
            data = doc.to_dict()
            food_name = data.get('food_name', 'Unknown')
            calories = data.get('calories', 0)
            total_calories += calories
            history_summary.append(f"- {food_name}: {calories} kcal")
            
        if not history_summary:
            return {
                "insight": "I need to see some of your meals before I can give advice. Start by analyzing a food photo!",
                "suggestions": ["Upload your first meal!", "Take a photo of your breakfast", "Track a snack"]
            }

        # 2. Call AI for coaching
        history_str = "\n".join(history_summary)
        prompt = f"""
        You are an expert Nutrition Coach. Based on the user's recent food history:
        {history_str}
        
        Total Calories in last 10 meals: {total_calories} kcal.
        
        Provide:
        1. A concise, encouraging 'Coach Insight' (max 2 sentences).
        2. Three specific 'Smart Meal Suggestions' for their next meal that would balance their diet.
        
        Return the result in strictly this JSON format:
        {{
            "insight": "your insight here",
            "suggestions": ["option 1", "option 2", "option 3"]
        }}
        """
        
        import json
        text_response = generate_text(prompt)
        
        # Clean and parse JSON
        text_response = text_response.replace("```json", "").replace("```", "").strip()
        result = json.loads(text_response)
        
        return result

    except Exception as e:
        print(f"Error in coaching: {e}")
        # Try a simpler query if ordering fails
        try:
             # Logic for simple coaching without ordering if firestore index is missing
             return {
                "insight": "You're doing a great job logging your food! Keep it up for more personalized insights.",
                "suggestions": ["Drink more water", "Eat more greens", "Try a high-protein breakfast"]
             }
        except:
            return {
                "insight": "I'm having a bit of trouble analyzing your data right now, but keep up the great work logging your meals!",
                "suggestions": ["Continue tracking your food", "Stay hydrated", "Aim for variety in your diet"]
            }

@app.post("/chat/{user_id}")
async def chat_with_ai(user_id: str, request: ChatRequest):
    """
    Interactive chat with AI about nutrition and food history.
    """
    if not db:
        raise HTTPException(status_code=503, detail="Database not initialized")
        
    try:
        from backend.memory_manager import memory_manager
        from ai_core.prompts import PERSONALIZED_CHAT_PROMPT
        
        # 1. Load user memories
        memories = memory_manager.get_user_memories(user_id)
        memory_context = memory_manager.format_memories_for_ai(memories)
        
        # 2. Fetch recent chat history for conversation context
        chat_ref = db.collection(u'chats')
        try:
            recent_chats = chat_ref.where(u'user_id', u'==', user_id).order_by(u'timestamp', direction=firestore.Query.DESCENDING).limit(10).stream()
            conversation_history = []
            for chat in recent_chats:
                chat_data = chat.to_dict()
                role = chat_data.get('role', 'user')
                content = chat_data.get('content', '')
                conversation_history.append(f"{role}: {content}")
            conversation_history.reverse()  # Chronological order
        except Exception as e:
            print(f"Error loading chat history: {e}")
            conversation_history = []
        
        conversation_str = "\n".join(conversation_history[-6:]) if conversation_history else "This is the start of the conversation."
        
        # 3. Get user name from Firebase
        try:
            user_ref = db.collection(u'users').document(user_id)
            user_doc = user_ref.get()
            user_name = user_doc.to_dict().get('full_name', 'User') if user_doc.exists else 'User'
        except:
            user_name = 'User'
        
        # 4. Build personalized prompt
        prompt = PERSONALIZED_CHAT_PROMPT.format(
            user_name=user_name,
            user_memories=memory_context,
            conversation_history=conversation_str,
            user_message=request.message
        )
        
        # 5. Generate AI response
        ai_response = generate_text(prompt)
        
        # 3. Store in Firebase
        try:
            chat_ref = db.collection(u'chats').document()
            chat_ref.set({
                u'user_id': user_id,
                u'role': u'user',
                u'content': request.message,
                u'timestamp': datetime.now()
            })
            chat_ref_ai = db.collection(u'chats').document()
            chat_ref_ai.set({
                u'user_id': user_id,
                u'role': u'assistant',
                u'content': ai_response,
                u'timestamp': datetime.now()
            })
        except Exception as e:
            print(f"Error saving chat to Firestore: {e}")

        return {"response": ai_response}

    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        with open("chat_error.log", "a") as f:
            f.write(f"\n--- Chat Error at {datetime.now()} ---\n")
            f.write(error_msg)
        print(f"❌ NutriChat Error: {e}")
        print(error_msg) # Print to console too
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

@app.post("/voice_chat/{user_id}")
async def voice_chat_with_ai(user_id: str, file: UploadFile = File(...)):
    """
    Handles audio recording and returns AI response.
    """
    if not db:
        raise HTTPException(status_code=503, detail="Database not initialized")
        
    try:
        # 1. Read audio bytes
        audio_bytes = await file.read()
        
        # 2. Fetch recent history for context (simplified)
        logs_ref = db.collection(u'food_logs')
        docs = logs_ref.where(u'user_id', u'==', user_id).limit(5).stream()
        history_context = []
        for doc in docs:
            data = doc.to_dict()
            food_name = data.get('food_name', 'Unknown')
            history_context.append(food_name)
        
        context_str = ", ".join(history_context) if history_context else "No meals logged yet."
        
        # 3. Build prompt for audio context
        prompt = f"""
        You are NutriVoice, an AI health assistant.
        User's recent food history: {context_str}
        
        Listen to the audio and provide:
        1. A 'transcription' of exactly what the user said (or a clear summary if noisy).
        2. A helpful and concise 'response' to their query.
        
        Return the result in strictly this JSON format:
        {{
            "transcription": "user speech here",
            "response": "your advice here"
        }}
        """
        
        # 4. Analyze Audio
        raw_ai_response = analyze_audio(audio_bytes, mime_type=file.content_type, prompt=prompt)
        
        import json
        try:
            # Clean and parse JSON
            clean_json = raw_ai_response.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean_json)
            transcription = result.get("transcription", "Voice Message")
            ai_response = result.get("response", raw_ai_response)
        except:
            transcription = "Voice Message"
            ai_response = raw_ai_response

        # 5. Store in Firebase
        try:
            chat_ref = db.collection(u'chats').document()
            chat_ref.set({
                u'user_id': user_id,
                u'role': u'user',
                u'content': f"🎤 {transcription}",
                u'timestamp': datetime.now()
            })
            chat_ref_ai = db.collection(u'chats').document()
            chat_ref_ai.set({
                u'user_id': user_id,
                u'role': u'assistant',
                u'content': ai_response,
                u'timestamp': datetime.now()
            })
        except Exception as e:
            print(f"Error saving voice chat to Firestore: {e}")

        return {"transcription": transcription, "response": ai_response}

    except Exception as e:
        print(f"❌ NutriVoice Error: {e}")
        raise HTTPException(status_code=500, detail=f"Voice processing failed: {str(e)}")

@app.get("/chats/{user_id}")
async def get_chats(user_id: str):
    """
    Fetches chat history for a specific user.
    """
    if not db:
        raise HTTPException(status_code=503, detail="Database not initialized")
        
    try:
        chats_ref = db.collection(u'chats')
        # Ordering by timestamp to get correct flow
        docs = chats_ref.where(u'user_id', u'==', user_id).order_by(u'timestamp', direction=firestore.Query.ASCENDING).stream()
        
        history = []
        for doc in docs:
            chat_data = doc.to_dict()
            history.append({
                "role": chat_data.get("role"),
                "content": chat_data.get("content")
            })
        return {"user_id": user_id, "history": history}
    except Exception as e:
        print(f"Error fetching chats: {e}")
        # Fallback without ordering
        try:
            docs = chats_ref.where(u'user_id', u'==', user_id).limit(20).stream()
            history = []
            for doc in docs:
                chat_data = doc.to_dict()
                history.append({
                    "role": chat_data.get("role"),
                    "content": chat_data.get("content")
                })
            return {"user_id": user_id, "history": history}
        except:
            raise HTTPException(status_code=500, detail=f"Failed to fetch chats: {str(e)}")


def _get_user_doc_by_email(users_ref, raw_email: str):
    email = raw_email.strip().lower()
    lookup_values = [
        ("email_normalized", email),
        ("email", email),
    ]

    stripped_email = raw_email.strip()
    if stripped_email and stripped_email != email:
        lookup_values.append(("email", stripped_email))

    for field, value in lookup_values:
        docs = users_ref.where(field, "==", value).limit(1).get()
        if docs:
            return docs[0]

    return None


@app.post("/register")
async def register_user(user: UserRegister):
    if not db:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    email = user.email.strip().lower()
    full_name = user.full_name.strip()

    try:
        # Check if user exists
        users_ref = db.collection("users")
        existing_user = _get_user_doc_by_email(users_ref, user.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="User with this email already exists")

        # Hash password
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), salt).decode('utf-8')

        # Create user
        new_user_ref = users_ref.document()
        new_user_ref.set({
            "full_name": full_name,
            "email": email,
            "email_normalized": email,
            "password": hashed_password,
            "created_at": datetime.now()
        })

        return {"message": "User registered successfully", "user_id": new_user_ref.id, "full_name": full_name}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Could not create account. Please try again.")

@app.post("/login")
async def login_user(user: UserLogin):
    if not db:
        raise HTTPException(status_code=503, detail="Database not initialized")

    try:
        users_ref = db.collection("users")
        user_doc = _get_user_doc_by_email(users_ref, user.email)

        if not user_doc:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        user_data = user_doc.to_dict() or {}
        stored_password = user_data.get("password")
        if not stored_password or not bcrypt.checkpw(user.password.encode('utf-8'), stored_password.encode('utf-8')):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        return {
            "message": "Login successful",
            "user_id": user_doc.id,
            "full_name": user_data.get("full_name", "User")
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Could not log in. Please try again.")
