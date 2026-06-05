import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogOut, ArrowLeft } from "lucide-react";

interface HeaderProps {
    title?: string;
    showBack?: boolean;
}

const Header: React.FC<HeaderProps> = ({ title, showBack }) => {
    const navigate = useNavigate();
    const userId = localStorage.getItem("user_id") || "demo_user";
    const fullName = localStorage.getItem("full_name") || "User Account";

    const [showUserMenu, setShowUserMenu] = useState(false);

    const handleLogout = () => {
        localStorage.removeItem("user_id");
        localStorage.removeItem("full_name");
        navigate("/signin");
    };

    return (
        <header className="flex items-center justify-between px-6 py-4 border-b border-border/50 backdrop-blur-md sticky top-0 z-50 bg-background/80">
            <div className="flex items-center gap-4">
                {showBack ? (
                    <button
                        onClick={() => navigate("/capture")}
                        className="w-10 h-10 rounded-full bg-secondary border border-border flex items-center justify-center hover:bg-secondary/80 transition-colors"
                    >
                        <ArrowLeft size={18} className="text-foreground" />
                    </button>
                ) : (
                    <div className="flex items-center gap-2 cursor-pointer" onClick={() => navigate("/capture")}>
                        <div>
                            <span className="font-semibold text-foreground">NutriLink</span>
                            <span className="text-[10px] text-muted-foreground block -mt-1 uppercase tracking-wider">Premium AI</span>
                        </div>
                    </div>
                )}
                {title && <h1 className="text-lg font-semibold text-foreground ml-2">{title}</h1>}
            </div>

            {!showBack && (
                <nav className="hidden md:flex items-center gap-8">
                    <button onClick={() => navigate("/capture")} className="text-primary font-medium text-sm border-b-2 border-primary pb-0.5">DASHBOARD</button>
                    <button onClick={() => navigate("/history")} className="text-muted-foreground font-medium text-sm hover:text-foreground transition-colors">HISTORY</button>
                    <button onClick={() => navigate("/statistics")} className="text-muted-foreground font-medium text-sm hover:text-foreground transition-colors">STATISTICS</button>
                </nav>
            )}

            <div className="flex items-center gap-4">
                {/* User Menu */}
                <div className="relative">
                    <button
                        onClick={() => {
                            setShowUserMenu(!showUserMenu);
                        }}
                        className="flex items-center gap-2 hover:bg-secondary/50 p-1.5 rounded-full transition-all duration-300"
                    >
                        <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center border border-border shadow-sm">
                            <span className="text-xs font-medium text-foreground">{fullName.split(' ').map(n => n[0]).join('') || "US"}</span>
                        </div>
                        <span className="text-sm text-foreground font-medium hidden md:block">{fullName.split(' ')[0] || "User"}</span>
                    </button>

                    {showUserMenu && (
                        <>
                            <div className="fixed inset-0 z-40" onClick={() => setShowUserMenu(false)} />
                            <div className="absolute right-0 mt-2 w-48 glass-card border border-border/50 rounded-2xl shadow-xl z-50 py-2 animate-in fade-in zoom-in duration-200 origin-top-right">
                                <div className="px-4 py-2 border-b border-border/50 mb-1">
                                    <p className="text-sm font-semibold text-foreground truncate">{fullName}</p>
                                    <p className="text-[10px] text-muted-foreground">Premium Account</p>
                                </div>
                                <button onClick={handleLogout} className="w-full flex items-center gap-2 px-4 py-2 text-sm text-destructive hover:bg-destructive/10 transition-colors">
                                    <LogOut size={16} /> Log Out
                                </button>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </header>
    );
};

export default Header;
