from engine.script_gen import generate_mixed_facts
import json

def test_distribution():
    print("🔬 Running Distribution Stress Test...")
    categories = ["science", "space", "anime_lore", "cooking_hacks"]
    
    for cat in categories:
        print(f"\n--- Category: {cat} ---")
        for i in range(3):
            facts = generate_mixed_facts(cat)
            trues = [f for f in facts if f['truth']]
            falses = [f for f in facts if not f['truth']]
            print(f"Run {i+1}: {len(trues)}T, {len(falses)}F")
            for j, f in enumerate(facts):
                print(f"  {j+1}. [{f['truth']}] {f['fact'][:60]}...")
            
            if len(trues) != 2 or len(falses) != 1:
                print("❌ FAIL: Wrong distribution!")
            else:
                print("✅ PASS: Correct distribution.")

if __name__ == "__main__":
    test_distribution()
