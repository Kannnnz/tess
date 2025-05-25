import requests
import json

def test_lm_studio_connection():
    """Test connection to LM Studio and model functionality"""
    
    base_url = "http://127.0.0.1:1234/v1"
    
    print("=== LM Studio Connection Test ===\n")
    
    # Test 1: Check if LM Studio is running
    print("1. Testing LM Studio connection...")
    try:
        response = requests.get(f"{base_url}/models", timeout=5)
        if response.status_code == 200:
            print("✅ LM Studio is running!")
        else:
            print(f"❌ LM Studio responded with status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to LM Studio!")
        print("Please make sure:")
        print("- LM Studio is running")
        print("- Server is started (click 'Start Server' in LM Studio)")
        print("- Server URL is http://127.0.0.1:1234")
        return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False
    
    # Test 2: Check available models
    print("\n2. Checking available models...")
    try:
        models = response.json()
        if models.get('data') and len(models['data']) > 0:
            model_name = models['data'][0]['id']
            print(f"✅ Model loaded: {model_name}")
        else:
            print("❌ No model loaded!")
            print("Please load a model in LM Studio (recommended: mistral-nemo-instruct-2407)")
            return False
    except Exception as e:
        print(f"❌ Error parsing models response: {e}")
        return False
    
    # Test 3: Test chat completion with short context
    print("\n3. Testing chat completion...")
    try:
        test_payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": "Halo, bisakah Anda membantu menganalisis dokumen penelitian?"
                }
            ],
            "max_tokens": 100,
            "temperature": 0.7,
            "stream": False
        }
        
        response = requests.post(
            f"{base_url}/chat/completions",
            json=test_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                reply = result['choices'][0]['message']['content']
                print("✅ Chat completion working!")
                print(f"Sample response: {reply[:100]}...")
            else:
                print("❌ Invalid response format")
                print(f"Response: {result}")
                return False
        else:
            print(f"❌ Chat completion failed with status {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timeout! Model might be too slow or overloaded")
        print("Try:")
        print("- Using a smaller/faster model")
        print("- Reducing max_tokens")
        print("- Increasing timeout")
        return False
    except Exception as e:
        print(f"❌ Chat completion error: {e}")
        return False
    
    # Test 4: Test with document context (simulate real usage)
    print("\n4. Testing with document context...")
    try:
        document_context = """
        Judul: Analisis Kinerja Sistem Informasi
        Abstrak: Penelitian ini menganalisis kinerja sistem informasi di universitas.
        Metode: Penelitian kuantitatif dengan survei kepada 100 responden.
        Hasil: Sistem informasi menunjukkan tingkat kepuasan 85%.
        """
        
        context_payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": f"Berdasarkan dokumen berikut:\n{document_context}\n\nApa metode penelitian yang digunakan?"
                }
            ],
            "max_tokens": 150,
            "temperature": 0.7,
            "stream": False
        }
        
        response = requests.post(
            f"{base_url}/chat/completions",
            json=context_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                reply = result['choices'][0]['message']['content']
                print("✅ Document analysis working!")
                print(f"Sample analysis: {reply[:150]}...")
            else:
                print("❌ Document analysis failed - invalid response")
                return False
        else:
            print(f"❌ Document analysis failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Document analysis error: {e}")
        return False
    
    print("\n✅ All tests passed! LM Studio is ready for use.")
    print("\nConfiguration Summary:")
    print(f"- Server URL: {base_url}")
    print(f"- Model: {model_name}")
    print("- Status: Ready")
    
    return True

def test_relevance_check():
    """Test relevance checking function"""
    print("\n=== Testing Relevance Check ===")
    
    def is_question_relevant(message: str) -> bool:
        keywords = [
            'paper', 'penelitian', 'skripsi', 'jurnal', 'artikel', 'studi', 'riset',
            'unnes', 'universitas negeri semarang', 'semarang', 'kampus',
            'metode', 'metodologi', 'hasil', 'kesimpulan', 'analisis',
            'penulis', 'author', 'abstrak', 'abstract', 'introduction',
            'diskusi', 'discussion', 'conclusion', 'reference', 'referensi'
        ]
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in keywords)
    
    test_questions = [
        ("Apa metode penelitian yang digunakan?", True),
        ("Siapa penulis paper ini?", True),
        ("Bagaimana dengan UNNES?", True),
        ("Apa itu nasi gudeg?", False),
        ("Bagaimana cuaca hari ini?", False),
        ("Analisis hasil penelitian ini", True),
        ("Universitas Negeri Semarang dimana?", True)
    ]
    
    for question, expected in test_questions:
        result = is_question_relevant(question)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{question}' -> {result} (expected: {expected})")

if __name__ == "__main__":
    # Test LM Studio connection
    lm_studio_ok = test_lm_studio_connection()
    
    # Test relevance checking
    test_relevance_check()
    
    if lm_studio_ok:
        print("\n🎉 Everything is working! You can now run:")
        print("python app.py")
    else:
        print("\n❌ Please fix LM Studio issues before running the main application.")
