import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY")

def generate_mixed_facts(category="science"):
    """
    Generates 2 True facts and 1 False fact using LLM with robust fallbacks.
    Returns a list of dicts: {"fact": str, "truth": bool}
    """
    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    
    model = "meta-llama/Llama-3.2-1B-Instruct" 
    
    prompt = f"""SPOT THE LIE! 🔍 One of these facts is a fake. Can you find it?
Generate three short, shocking facts about {category}. Exactly two must be true and one must be a believable lie.
If the category is '{category}' and it relates to anime/media, focus on specific plot points or "lore" (e.g., character actions or twists).
If the category relates to health or biology, focus on surprising scientific facts.
If the category relates to cooking, focus on kitchen secrets or food science.
Format as JSON ONLY. No other text. 
Example format:
[
  {{"fact": "...", "truth": true}},
  {{"fact": "...", "truth": true}},
  {{"fact": "...", "truth": false}}
]
"""
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
        "temperature": 0.9 # Higher temperature for more variety
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        if response.status_code != 200:
            print(f"DEBUG: API Error {response.status_code} - {response.text}")
        
        response.raise_for_status()
        output = response.json()["choices"][0]["message"]["content"]
        
        start = output.find("[")
        end = output.rfind("]") + 1
        facts = json.loads(output[start:end])
        
        # VALIDATION: Ensure exactly 2 True and 1 False
        trues = [f for f in facts if f.get("truth") == True]
        falses = [f for f in facts if f.get("truth") == False]
        
        if len(trues) == 2 and len(falses) == 1:
            for f in facts:
                # Remove common AI prefixes like "Fact 1: ", "1. ", "Fact: " etc.
                f["fact"] = f["fact"].split(": ", 1)[-1] if ": " in f["fact"] else f["fact"]
                if f["fact"].startswith(("1. ", "2. ", "3. ")):
                    f["fact"] = f["fact"][3:]
            return facts[:3]
        else:
            print(f"⚠️ LLM generated wrong counts ({len(trues)}T, {len(falses)}F). Reverting to fallback pool.")
        
    except Exception as e:
        print(f"💡 API unavailable or failed ({e}). Using expanded facts pool for variety.")
        
    # MASSIVE FALLBACK POOL (80+ facts)
    import random
    pool = {
        "science": [
            {"fact": "Bananas are radioactive because they contain potassium.", "truth": True},
            {"fact": "A teaspoonful of a neutron star would weigh 6 billion tons.", "truth": True},
            {"fact": "Sharks existed before trees.", "truth": True},
            {"fact": "Water can boil and freeze at the same time.", "truth": True},
            {"fact": "There are more trees on Earth than stars in the Milky Way.", "truth": True},
            {"fact": "Humans can smell rain due to a bacteria called Actinomycetes.", "truth": True},
            {"fact": "A single bolt of lightning has enough energy to toast 100,000 slices of bread.", "truth": True},
            {"fact": "The periodic table includes every letter except 'J'.", "truth": True},
            {"fact": "Helium can defy gravity and climb up the walls of a glass.", "truth": True},
            {"fact": "Diamond is not the hardest substance; Lonsdaleite is 58% harder.", "truth": True},
            {"fact": "Humans share 50% of their DNA with bananas.", "truth": True},
            {"fact": "The human stomach can dissolve razor blades in a few hours.", "truth": True},
            {"fact": "Humans can only use 10 percent of their brain capacity.", "truth": False},
            {"fact": "The Earth is perfectly spherical.", "truth": False},
            {"fact": "Glass is a slow-moving liquid.", "truth": False},
            {"fact": "Evolution is 'just a theory' and not proven.", "truth": False},
            {"fact": "Sunflowers follow the sun across the sky all day.", "truth": False},
            {"fact": "Lightning never strikes the same place twice.", "truth": False},
            {"fact": "Cracking your knuckles gives you arthritis.", "truth": False},
            {"fact": "Mount Everest is the closest point on Earth to space.", "truth": False} 
        ],
        "space": [
            {"fact": "One day on Venus is longer than one year on Earth.", "truth": True},
            {"fact": "There is a planet made primarily of diamonds called 55 Cancri e.", "truth": True},
            {"fact": "Neutron stars can spin at a rate of 600 rotations per second.", "truth": True},
            {"fact": "The footprints on the moon will stay there for 100 million years.", "truth": True},
            {"fact": "Space is completely silent because there is no air to carry sound.", "truth": True},
            {"fact": "Venus is the only planet that rotates clockwise.", "truth": True},
            {"fact": "Jupiter is twice as massive as all the other planets combined.", "truth": True},
            {"fact": "A day on Mercury lasts about 59 Earth days.", "truth": True},
            {"fact": "There is a massive water vapor cloud in space 12 billion light years away.", "truth": True},
            {"fact": "Halley's Comet won't return to the inner solar system until 2061.", "truth": True},
            {"fact": "The Sun makes up 99.86% of the mass in our solar system.", "truth": True},
            {"fact": "Saturn is the only planet in our solar system with rings.", "truth": False},
            {"fact": "The Sun is yellow in color.", "truth": False},
            {"fact": "Black holes are literal holes in space.", "truth": False},
            {"fact": "A 'light year' measures time.", "truth": False},
            {"fact": "The North Star is the brightest star in the night sky.", "truth": False}, 
            {"fact": "Astronauts get taller in space because there is zero gravity.", "truth": False}, 
            {"fact": "The Moon has a 'dark side' that never sees the sun.", "truth": False},
            {"fact": "Sound travels faster in space than on Earth.", "truth": False}
        ],
        "animals": [
            {"fact": "Cows have best friends and get stressed when separated.", "truth": True},
            {"fact": "A snail can sleep for three years.", "truth": True},
            {"fact": "Butterflies taste with their feet.", "truth": True},
            {"fact": "Koalas have unique fingerprints, just like humans.", "truth": True},
            {"fact": "A shrimp's heart is located in its head.", "truth": True},
            {"fact": "Ostriches can run faster than horses.", "truth": True},
            {"fact": "Sloths can hold their breath longer than dolphins.", "truth": True},
            {"fact": "A group of flamingos is called a 'flamboyance'.", "truth": True},
            {"fact": "Honeybees can recognize human faces.", "truth": True},
            {"fact": "Wombat poop is cube-shaped to stop it from rolling away.", "truth": True},
            {"fact": "Tardigrades can survive in the vacuum of space.", "truth": True},
            {"fact": "Goldfish have a 3 second memory.", "truth": False},
            {"fact": "Bulls hate the color red.", "truth": False},
            {"fact": "Dogs only see in black and white.", "truth": False},
            {"fact": "Chameleons change color to blend into their surroundings.", "truth": False},
            {"fact": "Bats are blind.", "truth": False},
            {"fact": "An elephant is the only animal that can't jump.", "truth": False}, 
            {"fact": "Touching a toad will give you warts.", "truth": False},
            {"fact": "Sharks can't get cancer.", "truth": False}
        ],
        "history": [
            {"fact": "Napoleon was actually of average height for his time.", "truth": True},
            {"fact": "Cleopatra lived closer to the invention of the iPhone than to the building of the Great Pyramid.", "truth": True},
            {"fact": "Albert Einstein was offered the presidency of Israel in 1952.", "truth": True},
            {"fact": "The Anglo-Zanzibar War of 1896 lasted only 38 minutes.", "truth": True},
            {"fact": "Romans used crushed mouse brains as toothpaste.", "truth": True},
            {"fact": "The first computer was invented in the 1830s by Charles Babbage.", "truth": True},
            {"fact": "The Great Wall of China is the only man-made structure visible from space.", "truth": False},
            {"fact": "Vikings wore horned helmets into battle.", "truth": False},
            {"fact": "Christopher Columbus discovered America.", "truth": False},
            {"fact": "The Titanic was advertised as 'unsinkable'.", "truth": False}
        ],
        "anime_lore": [
            {"fact": "Luffy defeated Crocodile in Alabasta by using blood to harden sand.", "truth": True},
            {"fact": "Zoro's sword, Shusui, was once considered a national treasure of Wano.", "truth": True},
            {"fact": "Itachi Uchiha killed his entire clan to prevent a civil war in the Hidden Leaf Village.", "truth": True},
            {"fact": "Goku's signature move, the Kamehameha, was invented by Master Roshi.", "truth": True},
            {"fact": "In Naruto, the Fourth Hokage was actually Naruto's father.", "truth": True},
            {"fact": "Luffy saved Crocodile in Alabasta to help him defeat the Marines.", "truth": False},
            {"fact": "Sasuke was the first person in the village to acknowledge Naruto's existence.", "truth": False},
            {"fact": "Light Yagami originally wanted to be a detective to find the real Kira.", "truth": False},
            {"fact": "Vegeta was the first character to reach Super Saiyan 3 in Dragon Ball Z.", "truth": False},
            {"fact": "One Piece is named after the 'One Piece' of advice Gold Roger gave to Luffy.", "truth": False}
        ],
        "intimacy_facts": [
            {"fact": "The human brain releases oxytocin during physical touch, often called the 'cuddle hormone'.", "truth": True},
            {"fact": "Kissing can burn up to 6.4 calories per minute.", "truth": True},
            {"fact": "Studies show that holding hands can significantly reduce stress and physical pain.", "truth": True},
            {"fact": "The smell of a partner can lower cortisol levels and induce relaxation.", "truth": True},
            {"fact": "Physical intimacy has been linked to a stronger immune system due to increased antibodies.", "truth": True},
            {"fact": "Humans are the only animals that have sex for pleasure rather than just procreation.", "truth": False},
            {"fact": "The average human spends one continuous month of their life kissing.", "truth": False},
            {"fact": "You can catch a cold just by thinking about someone who has one during a date.", "truth": False},
            {"fact": "The heart physically changes shape into a heart symbol when you fall in love.", "truth": False},
            {"fact": "Men and women have the exact same physiological response to romantic movies.", "truth": False}
        ],
        "cooking_hacks": [
            {"fact": "Adding a pinch of salt to coffee can reduce its bitterness.", "truth": True},
            {"fact": "Storing potatoes with apples can prevent the potatoes from sprouting.", "truth": True},
            {"fact": "You can use a glass of water in the microwave to keep pizza crust from getting soggy.", "truth": True},
            {"fact": "Putting an onion in the freezer for 15 minutes before cutting can stop the crying effect.", "truth": True},
            {"fact": "Mushrooms are made of 90% water, which is why they shrink so much when cooked.", "truth": True},
            {"fact": "Adding olive oil to boiling water prevents pasta from sticking together.", "truth": False},
            {"fact": "White chocolate is technically chocolate because it contains cocoa solids.", "truth": False},
            {"fact": "Putting a wooden spoon over a boiling pot of water will always stop it from overflowing.", "truth": False},
            {"fact": "Sealing the tail of a banana with plastic wrap will keep it fresh for an extra month.", "truth": False},
            {"fact": "Adding baking soda to onions makes them caramelize slower.", "truth": False}
        ]
    }
    
    # Select category with a fallback to random choice for more variety
    cat_keys = list(pool.keys())
    selected_cat = category.lower() if category.lower() in cat_keys else random.choice(cat_keys)
    selected = pool[selected_cat]
    random.shuffle(selected)
    
    # Filter trues and falses
    trues = [f for f in selected if f["truth"]]
    falses = [f for f in selected if not f["truth"]]
    
    if len(trues) >= 2 and len(falses) >= 1:
        # Pick 2 random trues and 1 random false
        final_facts = random.sample(trues, 2) + random.sample(falses, 1)
        random.shuffle(final_facts)
        return final_facts
    
    return selected[:3]

if __name__ == "__main__":
    facts = generate_mixed_facts("science")
    for i, f in enumerate(facts):
        print(f"{i+1}. {f['fact']} (True: {f['truth']})")
