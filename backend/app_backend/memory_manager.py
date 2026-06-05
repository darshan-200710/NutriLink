"""
Memory Manager for Personalized Food Intelligence
Handles storage and retrieval of user-specific eating patterns and habits.
"""
from backend.firebase_utils import db
from datetime import datetime
from typing import Dict, Any, Optional
import json


class MemoryManager:
    """Manages user food memories in Firebase"""
    
    def __init__(self):
        self.collection = "user_food_memories"
    
    def get_user_memories(self, user_id: str) -> Dict[str, Any]:
        """
        Retrieve all memories for a specific user.
        Returns empty structure if no memories exist.
        """
        try:
            doc_ref = db.collection(self.collection).document(user_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            else:
                # Return empty memory structure
                return self._empty_memory_structure()
        except Exception as e:
            print(f"Error retrieving memories for {user_id}: {e}")
            return self._empty_memory_structure()
    
    def _empty_memory_structure(self) -> Dict[str, Any]:
        """Return empty memory structure"""
        return {
            "portion_sizes": {},
            "meal_frequencies": {},
            "timing_patterns": {},
            "preferences": {
                "likes": [],
                "avoids": [],
                "dietary_notes": ""
            },
            "updated_at": datetime.utcnow().isoformat()
        }
    
    def update_portion_memory(self, user_id: str, food_name: str, portion_data: Dict[str, Any]):
        """
        Update portion size memory for a specific food.
        
        Args:
            user_id: User identifier
            food_name: Name of the food (normalized)
            portion_data: Dict with 'amount', 'unit', 'confidence'
        """
        try:
            doc_ref = db.collection(self.collection).document(user_id)
            memories = self.get_user_memories(user_id)
            
            # Update or create portion memory
            if food_name in memories["portion_sizes"]:
                # Calculate running average
                existing = memories["portion_sizes"][food_name]
                count = existing.get("count", 1)
                old_avg = existing.get("average", portion_data["amount"])
                new_avg = (old_avg * count + portion_data["amount"]) / (count + 1)
                
                memories["portion_sizes"][food_name] = {
                    "average": round(new_avg, 2),
                    "unit": portion_data["unit"],
                    "confidence": min(0.95, existing.get("confidence", 0.5) + 0.1),
                    "count": count + 1,
                    "last_updated": datetime.utcnow().isoformat()
                }
            else:
                memories["portion_sizes"][food_name] = {
                    "average": portion_data["amount"],
                    "unit": portion_data["unit"],
                    "confidence": 0.6,
                    "count": 1,
                    "last_updated": datetime.utcnow().isoformat()
                }
            
            memories["updated_at"] = datetime.utcnow().isoformat()
            doc_ref.set(memories)
            
        except Exception as e:
            print(f"Error updating portion memory: {e}")
    
    def update_frequency_memory(self, user_id: str, food_name: str, nutrition_data: Dict[str, Any]):
        """
        Update meal frequency memory.
        
        Args:
            user_id: User identifier
            food_name: Name of the food
            nutrition_data: Dict with 'calories', 'protein_g', etc.
        """
        try:
            doc_ref = db.collection(self.collection).document(user_id)
            memories = self.get_user_memories(user_id)
            
            if food_name in memories["meal_frequencies"]:
                existing = memories["meal_frequencies"][food_name]
                count = existing.get("count", 0)
                old_avg_cal = existing.get("avg_calories", nutrition_data.get("calories", 0))
                new_avg_cal = (old_avg_cal * count + nutrition_data.get("calories", 0)) / (count + 1)
                
                memories["meal_frequencies"][food_name] = {
                    "count": count + 1,
                    "last_seen": datetime.utcnow().isoformat(),
                    "avg_calories": round(new_avg_cal, 0),
                    "avg_protein": round((existing.get("avg_protein", 0) * count + nutrition_data.get("protein_g", 0)) / (count + 1), 1),
                    "avg_carbs": round((existing.get("avg_carbs", 0) * count + nutrition_data.get("carbs_g", 0)) / (count + 1), 1),
                    "avg_fats": round((existing.get("avg_fats", 0) * count + nutrition_data.get("fats_g", 0)) / (count + 1), 1)
                }
            else:
                memories["meal_frequencies"][food_name] = {
                    "count": 1,
                    "last_seen": datetime.utcnow().isoformat(),
                    "avg_calories": nutrition_data.get("calories", 0),
                    "avg_protein": nutrition_data.get("protein_g", 0),
                    "avg_carbs": nutrition_data.get("carbs_g", 0),
                    "avg_fats": nutrition_data.get("fats_g", 0)
                }
            
            memories["updated_at"] = datetime.utcnow().isoformat()
            doc_ref.set(memories)
            
        except Exception as e:
            print(f"Error updating frequency memory: {e}")
    
    def update_timing_pattern(self, user_id: str, meal_type: str, food_name: str, time_str: str):
        """
        Update meal timing patterns.
        
        Args:
            user_id: User identifier
            meal_type: 'breakfast', 'lunch', 'dinner', 'snack'
            food_name: Name of the food
            time_str: Time in HH:MM format
        """
        try:
            doc_ref = db.collection(self.collection).document(user_id)
            memories = self.get_user_memories(user_id)
            
            if meal_type not in memories["timing_patterns"]:
                memories["timing_patterns"][meal_type] = {
                    "typical_time": time_str,
                    "foods": [food_name]
                }
            else:
                if food_name not in memories["timing_patterns"][meal_type]["foods"]:
                    memories["timing_patterns"][meal_type]["foods"].append(food_name)
            
            memories["updated_at"] = datetime.utcnow().isoformat()
            doc_ref.set(memories)
            
        except Exception as e:
            print(f"Error updating timing pattern: {e}")
    
    def check_eating_limit(self, user_id: str, food_name: str) -> Optional[Dict[str, Any]]:
        """
        Check if user has reached their typical eating limit for a specific food today.
        
        Args:
            user_id: User identifier
            food_name: Normalized food name
            
        Returns:
            Dict with limit info if limit reached, None otherwise
            Format: {"reached": True, "count": 2, "food": "pizza", "message": "..."}
        """
        try:
            from datetime import datetime, timedelta
            from backend.firebase_utils import db
            
            # Get user memories
            memories = self.get_user_memories(user_id)
            
            # Check if we have frequency data for this food
            if food_name not in memories.get("meal_frequencies", {}):
                return None  # No pattern learned yet
            
            freq_data = memories["meal_frequencies"][food_name]
            typical_count = freq_data.get("count", 0)
            
            # Need at least 3 occurrences to establish a pattern
            if typical_count < 3:
                return None
            
            # Count how many times this food was eaten TODAY
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            logs_ref = db.collection(u'food_logs')
            today_docs = logs_ref.where(u'user_id', u'==', user_id).stream()
            
            today_count = 0
            for doc in today_docs:
                data = doc.to_dict()
                timestamp = data.get('timestamp')
                if timestamp:
                    # Handle both datetime objects and ISO strings
                    if isinstance(timestamp, str):
                        doc_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    else:
                        doc_time = timestamp
                    
                    if doc_time >= today_start:
                        from backend.pattern_analyzer import PatternAnalyzer
                        doc_food = PatternAnalyzer.normalize_food_name(data.get('food_name', ''))
                        if doc_food == food_name:
                            today_count += 1
            
            # Calculate typical daily limit (average occurrences per day over history)
            # Simplified: if they've eaten it 5+ times total, typical limit is ~2 per day
            # If 10+ times, limit is ~3 per day
            if typical_count >= 10:
                typical_daily_limit = 3
            elif typical_count >= 5:
                typical_daily_limit = 2
            else:
                typical_daily_limit = 1
            
            # Check if limit reached
            if today_count >= typical_daily_limit:
                return {
                    "reached": True,
                    "count": today_count,
                    "food": food_name,
                    "typical_limit": typical_daily_limit,
                    "message": f"You've eaten {today_count} {food_name} — this is typically your max for today."
                }
            
            return None
            
        except Exception as e:
            print(f"Error checking eating limit: {e}")
            return None
    
    def format_memories_for_ai(self, memories: Dict[str, Any]) -> str:
        """
        Format memories into a natural language string for AI context.
        
        Args:
            memories: User memory dictionary
            
        Returns:
            Formatted string for AI prompt
        """
        if not memories or memories == self._empty_memory_structure():
            return "No learned patterns yet. This is your first interaction with this user."
        
        formatted = []
        
        # Portion sizes
        if memories.get("portion_sizes"):
            formatted.append("**Typical Portions:**")
            for food, data in list(memories["portion_sizes"].items())[:5]:  # Top 5
                if data.get("count", 0) >= 2:  # Only if seen multiple times
                    formatted.append(f"- {food}: usually {data['average']} {data['unit']}")
        
        # Meal frequencies
        if memories.get("meal_frequencies"):
            formatted.append("\n**Frequent Meals:**")
            sorted_meals = sorted(
                memories["meal_frequencies"].items(),
                key=lambda x: x[1].get("count", 0),
                reverse=True
            )[:5]
            for food, data in sorted_meals:
                if data.get("count", 0) >= 3:
                    formatted.append(
                        f"- {food}: eaten {data['count']} times, "
                        f"averages ~{data['avg_calories']} cal"
                    )
        
        # Timing patterns
        if memories.get("timing_patterns"):
            formatted.append("\n**Meal Timing:**")
            for meal_type, data in memories["timing_patterns"].items():
                if data.get("foods"):
                    foods_str = ", ".join(data["foods"][:3])
                    formatted.append(f"- {meal_type.title()}: typically {data.get('typical_time', 'varies')} ({foods_str})")
        
        # Preferences
        if memories.get("preferences"):
            prefs = memories["preferences"]
            if prefs.get("likes"):
                formatted.append(f"\n**Likes:** {', '.join(prefs['likes'][:5])}")
            if prefs.get("avoids"):
                formatted.append(f"**Avoids:** {', '.join(prefs['avoids'][:5])}")
            if prefs.get("dietary_notes"):
                formatted.append(f"**Dietary:** {prefs['dietary_notes']}")
        
        return "\n".join(formatted) if formatted else "No significant patterns learned yet."


# Global instance
memory_manager = MemoryManager()
