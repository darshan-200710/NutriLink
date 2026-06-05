"""
Pattern Analyzer for Food Intelligence
Detects eating patterns, habits, and trends from user food history.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
import re


class PatternAnalyzer:
    """Analyzes food history to detect patterns and habits"""
    
    @staticmethod
    def normalize_food_name(food_name: str) -> str:
        """
        Normalize food names for consistent pattern matching.
        Examples: "Chicken Biryani" -> "biryani", "2 Rotis" -> "roti"
        """
        # Convert to lowercase
        name = food_name.lower().strip()
        
        # Remove numbers and common words
        name = re.sub(r'\d+', '', name)
        name = re.sub(r'\b(with|and|or|the|a|an)\b', '', name)
        
        # Remove extra spaces
        name = ' '.join(name.split())
        
        # Singularize common plurals
        if name.endswith('s') and len(name) > 3:
            name = name[:-1]
        
        return name.strip()
    
    @staticmethod
    def detect_portion_pattern(food_history: List[Dict[str, Any]], food_name: str) -> Optional[Dict[str, Any]]:
        """
        Detect typical portion size for a specific food.
        
        Args:
            food_history: List of food entries with 'food_name' and estimated portions
            food_name: Normalized food name to analyze
            
        Returns:
            Dict with average portion, unit, and confidence
        """
        normalized_name = PatternAnalyzer.normalize_food_name(food_name)
        portions = []
        
        for entry in food_history:
            entry_name = PatternAnalyzer.normalize_food_name(entry.get("food_name", ""))
            if normalized_name in entry_name or entry_name in normalized_name:
                # Extract portion from description or estimate from calories
                portion = entry.get("portion_size")
                if portion:
                    portions.append(portion)
        
        if len(portions) >= 2:
            avg_portion = sum(portions) / len(portions)
            return {
                "amount": round(avg_portion, 1),
                "unit": "servings",  # Could be improved with unit detection
                "confidence": min(0.9, 0.5 + (len(portions) * 0.1))
            }
        
        return None
    
    @staticmethod
    def detect_meal_timing(food_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect typical meal timing patterns.
        
        Args:
            food_history: List of food entries with timestamps
            
        Returns:
            Dict mapping meal types to typical times
        """
        timing_data = defaultdict(list)
        
        for entry in food_history:
            timestamp = entry.get("timestamp")
            if not timestamp:
                continue
            
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                hour = dt.hour
                
                # Classify meal type by hour
                if 5 <= hour < 11:
                    meal_type = "breakfast"
                elif 11 <= hour < 16:
                    meal_type = "lunch"
                elif 16 <= hour < 19:
                    meal_type = "snack"
                else:
                    meal_type = "dinner"
                
                timing_data[meal_type].append({
                    "hour": hour,
                    "minute": dt.minute,
                    "food": entry.get("food_name", "")
                })
            except:
                continue
        
        # Calculate typical times
        patterns = {}
        for meal_type, times in timing_data.items():
            if len(times) >= 3:
                avg_hour = sum(t["hour"] for t in times) / len(times)
                avg_minute = sum(t["minute"] for t in times) / len(times)
                
                patterns[meal_type] = {
                    "typical_time": f"{int(avg_hour):02d}:{int(avg_minute):02d}",
                    "foods": list(set(t["food"] for t in times))[:5]
                }
        
        return patterns
    
    @staticmethod
    def detect_frequency_trends(food_history: List[Dict[str, Any]], days: int = 30) -> Dict[str, Any]:
        """
        Detect which foods are eaten most frequently.
        
        Args:
            food_history: List of food entries
            days: Number of days to analyze
            
        Returns:
            Dict mapping food names to frequency data
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        food_counts = defaultdict(lambda: {
            "count": 0,
            "total_calories": 0,
            "total_protein": 0,
            "total_carbs": 0,
            "total_fats": 0,
            "last_seen": None
        })
        
        for entry in food_history:
            timestamp = entry.get("timestamp")
            if not timestamp:
                continue
            
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                if dt < cutoff_date:
                    continue
                
                food_name = PatternAnalyzer.normalize_food_name(entry.get("food_name", ""))
                if not food_name:
                    continue
                
                food_counts[food_name]["count"] += 1
                food_counts[food_name]["total_calories"] += entry.get("calories", 0)
                food_counts[food_name]["total_protein"] += entry.get("protein_g", 0)
                food_counts[food_name]["total_carbs"] += entry.get("carbs_g", 0)
                food_counts[food_name]["total_fats"] += entry.get("fats_g", 0)
                
                if not food_counts[food_name]["last_seen"] or dt > datetime.fromisoformat(food_counts[food_name]["last_seen"]):
                    food_counts[food_name]["last_seen"] = dt.isoformat()
            except:
                continue
        
        # Calculate averages
        frequency_data = {}
        for food, data in food_counts.items():
            if data["count"] >= 2:  # Only include foods eaten at least twice
                frequency_data[food] = {
                    "count": data["count"],
                    "last_seen": data["last_seen"],
                    "avg_calories": round(data["total_calories"] / data["count"], 0),
                    "avg_protein": round(data["total_protein"] / data["count"], 1),
                    "avg_carbs": round(data["total_carbs"] / data["count"], 1),
                    "avg_fats": round(data["total_fats"] / data["count"], 1)
                }
        
        return frequency_data
    
    @staticmethod
    def detect_preferences(food_history: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """
        Detect food preferences based on frequency and variety.
        
        Args:
            food_history: List of food entries
            
        Returns:
            Dict with 'likes' and 'avoids' lists
        """
        frequency = PatternAnalyzer.detect_frequency_trends(food_history, days=60)
        
        # Foods eaten 5+ times are likely favorites
        likes = [
            food for food, data in frequency.items()
            if data["count"] >= 5
        ]
        
        # Sort by frequency
        likes = sorted(likes, key=lambda f: frequency[f]["count"], reverse=True)[:10]
        
        return {
            "likes": likes,
            "avoids": [],  # Could be detected from explicit user feedback
            "dietary_notes": ""  # Could be inferred from patterns
        }
    
    @staticmethod
    def analyze_all_patterns(food_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run all pattern detection algorithms on food history.
        
        Args:
            food_history: List of food entries
            
        Returns:
            Complete pattern analysis
        """
        return {
            "timing_patterns": PatternAnalyzer.detect_meal_timing(food_history),
            "meal_frequencies": PatternAnalyzer.detect_frequency_trends(food_history),
            "preferences": PatternAnalyzer.detect_preferences(food_history)
        }


# Global instance
pattern_analyzer = PatternAnalyzer()
