import sys
import os

# Add the current directory to sys.path to import engine
sys.path.append(os.getcwd())

from engine.script_gen import generate_mixed_facts

def test_category(category):
    print(f"\n--- Testing Category: {category} ---")
    try:
        facts = generate_mixed_facts(category)
        if not facts or len(facts) < 3:
            print(f"❌ Error: {category} returned less than 3 facts.")
            return False
        
        trues = [f for f in facts if f['truth']]
        falses = [f for f in facts if not f['truth']]
        
        print(f"✅ Generated {len(facts)} facts.")
        print(f"✅ True facts: {len(trues)}")
        print(f"✅ False facts: {len(falses)}")
        
        for i, f in enumerate(facts):
            status = "TRUE" if f['truth'] else "FALSE"
            print(f"   {i+1}. [{status}] {f['fact']}")
            
        if len(trues) == 2 and len(falses) == 1:
            print(f"✨ {category} passed!")
            return True
        else:
            print(f"❌ {category} failed (Expected 2 True, 1 False).")
            return False
    except Exception as e:
        print(f"❌ Exception testing {category}: {e}")
        return False

if __name__ == "__main__":
    results = []
    results.append(test_category("anime"))
    results.append(test_category("superheroes"))
    
    if all(results):
        print("\n🎉 ALL NEW CATEGORY TESTS PASSED!")
    else:
        print("\n⚠️ SOME TESTS FAILED.")
        sys.exit(1)
