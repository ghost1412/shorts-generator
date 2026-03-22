import json
from engine.script_gen import generate_mixed_facts

def test():
    print("Testing generate_mixed_facts...")
    try:
        result = generate_mixed_facts(category="science")
        print("\n=== GENERATED SCRIPT ===")
        print(json.dumps(result, indent=2))
        print("========================")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
