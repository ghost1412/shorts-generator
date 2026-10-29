import os
import sys
import json
from unittest.mock import patch, MagicMock

# Add current dir to path
sys.path.append(os.getcwd())

from engine.script_gen import generate_odd_one_out_script
from engine.media_gen import get_game_assets

def test_odd_variety():
    print("🧪 Testing ODD_ONE_OUT Variety Boost...")
    
    # 1. Test Script Generation
    print("Step 1: Testing script generation with new fields...")
    try:
        res = generate_odd_one_out_script("animals")
        print(f"✅ LLM Response contains target_query: '{res.get('target_query')}'")
        print(f"✅ LLM Response contains distractor_query: '{res.get('distractor_query')}'")
        
        if not res.get("target_query") or not res.get("distractor_query"):
            print("❌ Error: Missing required query fields in LLM response.")
            return False
            
    except Exception as e:
        print(f"❌ Script generation failed: {e}")
        return False

    # 2. Test Media Fetching
    print("\nStep 2: Testing media fetching with LLM queries...")
    test_dir = "assets/test_variety"
    os.makedirs(test_dir, exist_ok=True)
    
    try:
        assets = get_game_assets(
            num_objects=3, 
            target_query=res["target_query"], 
            distractor_query=res["distractor_query"],
            output_dir=test_dir
        )
        
        print(f"✅ Assets fetched for target: '{assets['target_name']}'")
        print(f"✅ Target path: {assets['target_path']}")
        print(f"✅ Distractor count: {len(assets['objects'])}")
        
        if not assets["target_path"] or len(assets["objects"]) == 0:
            print("❌ Error: Assets were not downloaded correctly.")
            return False
            
        print("✅ Media fetching verification passed.")
        
    except Exception as e:
        print(f"❌ Media fetching failed: {e}")
        return False

    print("\n🎉 ODD_ONE_OUT Variety Boost Verification PASSED!")
    return True

if __name__ == "__main__":
    test_odd_variety()
