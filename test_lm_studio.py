import requests
import json
import time
import sys
from datetime import datetime

# LM Studio configuration
LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL_NAME = "mistral-nemo-instruct-2407"

def test_connection():
    """Test basic connection to LM Studio"""
    try:
        # Simple health check
        health_url = "http://127.0.0.1:1234/health"
        response = requests.get(health_url, timeout=5)
        
        if response.status_code == 200:
            print("✅ LM Studio connection: OK")
            return True
        else:
            print(f"⚠️ LM Studio health check returned: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to LM Studio")
        print("💡 Make sure LM Studio is running on http://127.0.0.1:1234")
        return False
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def create_system_prompt():
    """Create the system prompt for document analysis"""
    return """Anda adalah asisten AI yang bertugas membantu menganalisis dokumen penelitian dan menjawab pertanyaan tentang Universitas Negeri Semarang (UNNES).

ATURAN PENTING:
1. Hanya jawab pertanyaan yang berkaitan dengan:
   - Analisis dokumen/paper/penelitian/skripsi yang diberikan
   - Informasi tentang Universitas Negeri Semarang (UNNES)

2. Jika pertanyaan TIDAK berkaitan dengan paper atau UNNES, jawab dengan:
   "Maaf, tolong berikan pertanyaan yang relevan dengan paper atau Universitas Negeri Semarang."

3. Berikan jawaban yang akurat berdasarkan dokumen yang diberikan
4. Jika informasi tidak tersedia dalam dokumen, sampaikan dengan jelas
5. Gunakan bahasa Indonesia yang formal dan profesional

FOKUS UTAMA:
- Analisis metodologi penelitian
- Identifikasi hasil dan kesimpulan
- Informasi penulis dan publikasi
- Kontribusi penelitian
- Informasi tentang UNNES (sejarah, fakultas, program studi, dll)"""

def send_chat_request(message, document_content="", is_relevance_check=False):
    """
    Send chat request to LM Studio
    
    Args:
        message (str): User message/question
        document_content (str): Document content for analysis
        is_relevance_check (bool): Whether this is a relevance check
    
    Returns:
        dict: Response from LM Studio
    """
    
    if is_relevance_check:
        # Special prompt for relevance checking
        system_prompt = """Periksa apakah pertanyaan berikut berkaitan dengan:
1. Analisis dokumen/paper/penelitian/skripsi
2. Universitas Negeri Semarang (UNNES)

Jawab hanya dengan "RELEVAN" atau "TIDAK RELEVAN"."""
        
        user_message = f"Pertanyaan: {message}"
    else:
        system_prompt = create_system_prompt()
        
        if document_content:
            user_message = f"""DOKUMEN YANG DIANALISIS:
{document_content[:3000]}  

PERTANYAAN: {message}

Jawab berdasarkan dokumen di atas."""
        else:
            user_message = message
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user", 
                "content": user_message
            }
        ],
        "temperature": 0.7,
        "max_tokens": 1000,
        "stream": False
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            LM_STUDIO_URL,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=60
        )
        end_time = time.time()
        
        response_time = round((end_time - start_time) * 1000)  # Convert to milliseconds
        
        if response.status_code == 200:
            result = response.json()
            
            return {
                "success": True,
                "response": result["choices"][0]["message"]["content"],
                "response_time_ms": response_time,
                "token_usage": result.get("usage", {}),
                "model": MODEL_NAME
            }
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}",
                "response_time_ms": response_time
            }
            
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Request timeout (60 seconds)",
            "response_time_ms": 60000
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "response_time_ms": 0
        }

def test_relevance_checking():
    """Test the relevance checking functionality"""
    
    print("\n🔍 Testing Relevance Checking")
    print("="*40)
    
    test_cases = [
        ("Apa metode penelitian yang digunakan dalam paper ini?", True),
        ("Siapa penulis paper ini?", True),
        ("Bagaimana sejarah UNNES?", True),
        ("Apa saja fakultas di Universitas Negeri Semarang?", True),
        ("Bagaimana cara memasak nasi goreng?", False),
        ("Siapa presiden Indonesia?", False),
        ("Apa hasil penelitian dalam skripsi ini?", True),
        ("Bagaimana cuaca hari ini?", False)
    ]
    
    correct_predictions = 0
    
    for question, expected_relevant in test_cases:
        print(f"\n📝 Question: {question}")
        print(f"Expected: {'RELEVAN' if expected_relevant else 'TIDAK RELEVAN'}")
        
        result = send_chat_request(question, is_relevance_check=True)
        
        if result["success"]:
            response = result["response"].strip().upper()
            is_relevant = "RELEVAN" in response and "TIDAK RELEVAN" not in response
            
            print(f"AI Response: {result['response']}")
            print(f"Predicted: {'RELEVAN' if is_relevant else 'TIDAK RELEVAN'}")
            print(f"Time: {result['response_time_ms']}ms")
            
            if is_relevant == expected_relevant:
                print("✅ CORRECT")
                correct_predictions += 1
            else:
                print("❌ INCORRECT")
        else:
            print(f"❌ Error: {result['error']}")
    
    accuracy = (correct_predictions / len(test_cases)) * 100
    print(f"\n📊 Relevance Check Accuracy: {accuracy:.1f}% ({correct_predictions}/{len(test_cases)})")

def test_document_analysis():
    """Test document analysis with sample content"""
    
    print("\n📄 Testing Document Analysis")
    print("="*40)
    
    # Sample document content
    sample_document = """
    Judul: Analisis Pengaruh Media Pembelajaran Digital Terhadap Prestasi Belajar Siswa
    
    Penulis: Dr. Ahmad Subandi, M.Pd
    Universitas Negeri Semarang
    
    ABSTRAK
    Penelitian ini bertujuan untuk menganalisis pengaruh penggungan media pembelajaran digital 
    terhadap prestasi belajar siswa di era teknologi modern. Metode yang digunakan adalah 
    penelitian kuantitatif dengan pendekatan eksperimen. Sample penelitian sebanyak 60 siswa 
    yang dibagi menjadi dua kelompok.
    
    METODOLOGI
    Penelitian ini menggunakan metode eksperimen dengan desain pretest-posttest control group.
    Kelompok eksperimen menggunakan media pembelajaran digital, sedangkan kelompok kontrol
    menggunakan metode pembelajaran konvensional.
    
    HASIL PENELITIAN
    Hasil analisis menunjukkan bahwa terdapat perbedaan signifikan antara prestasi belajar
    kelompok eksperimen dan kelompok kontrol (p < 0.05). Kelompok yang menggunakan media
    digital menunjukkan peningkatan prestasi belajar sebesar 23%.
    
    KESIMPULAN
    Media pembelajaran digital terbukti efektif meningkatkan prestasi belajar siswa.
    Penelitian ini merekomendasikan penggunaan teknologi digital dalam proses pembelajaran.
    """
    
    test_questions = [
        "Apa metode penelitian yang digunakan dalam paper ini?",
        "Siapa penulis penelitian ini?",
        "Apa hasil utama dari penelitian ini?",
        "Apa kesimpulan dari penelitian ini?",
        "Berapa sample yang digunakan dalam penelitian?"
    ]
    
    for question in test_questions:
        print(f"\n❓ Question: {question}")
        
        result = send_chat_request(question, sample_document)
        
        if result["success"]:
            print(f"✅ Answer: {result['response']}")
            print(f"⏱️ Response time: {result['response_time_ms']}ms")
            
            if result.get("token_usage"):
                usage = result["token_usage"]
                print(f"🔢 Tokens - Prompt: {usage.get('prompt_tokens', 'N/A')}, "
                      f"Completion: {usage.get('completion_tokens', 'N/A')}, "
                      f"Total: {usage.get('total_tokens', 'N/A')}")
        else:
            print(f"❌ Error: {result['error']}")

def test_unnes_questions():
    """Test UNNES-related questions"""
    
    print("\n🏛️ Testing UNNES Questions")
    print("="*40)
    
    unnes_questions = [
        "Bagaimana sejarah Universitas Negeri Semarang?",
        "Apa saja fakultas yang ada di UNNES?",
        "Apa visi dan misi UNNES?",
        "Dimana lokasi kampus UNNES?",
        "Apa saja program studi unggulan di UNNES?"
    ]
    
    for question in unnes_questions:
        print(f"\n❓ Question: {question}")
        
        result = send_chat_request(question)
        
        if result["success"]:
            print(f"✅ Answer: {result['response'][:200]}...")
            print(f"⏱️ Response time: {result['response_time_ms']}ms")
        else:
            print(f"❌ Error: {result['error']}")

def test_irrelevant_questions():
    """Test irrelevant questions that should be rejected"""
    
    print("\n🚫 Testing Irrelevant Questions")
    print("="*40)
    
    irrelevant_questions = [
        "Bagaimana cara memasak rendang?",
        "Siapa presiden Indonesia saat ini?",
        "Bagaimana cuaca hari ini?",
        "Kapan pertandingan sepak bola nanti?",
        "Apa resep kue tart yang enak?"
    ]
    
    expected_response = "Maaf, tolong berikan pertanyaan yang relevan dengan paper atau Universitas Negeri Semarang"
    
    correct_rejections = 0
    
    for question in irrelevant_questions:
        print(f"\n❓ Question: {question}")
        
        result = send_chat_request(question)
        
        if result["success"]:
            response = result['response']
            print(f"🤖 Response: {response}")
            
            # Check if the response contains the expected rejection message
            if "relevan dengan paper atau" in response.lower() or "universitas negeri semarang" in response.lower():
                print("✅ CORRECTLY REJECTED")
                correct_rejections += 1
            else:
                print("❌ SHOULD HAVE BEEN REJECTED")
            
            print(f"⏱️ Response time: {result['response_time_ms']}ms")
        else:
            print(f"❌ Error: {result['error']}")
    
    rejection_rate = (correct_rejections / len(irrelevant_questions)) * 100
    print(f"\n📊 Rejection Rate: {rejection_rate:.1f}% ({correct_rejections}/{len(irrelevant_questions)})")

def performance_benchmark():
    """Run performance benchmark"""
    
    print("\n⚡ Performance Benchmark")
    print("="*40)
    
    # Test different question lengths
    test_cases = [
        ("Short question", "Apa metode penelitian ini?"),
        ("Medium question", "Bisa dijelaskan apa saja metodologi penelitian yang digunakan dalam paper ini dan bagaimana implementasinya?"),
        ("Long question", "Mohon analisis komprehensif mengenai metodologi penelitian yang digunakan dalam paper ini, termasuk desain penelitian, teknik sampling, instrumen penelitian, metode analisis data, dan bagaimana validitas serta reliabilitas penelitian dijaga dalam study ini?")
    ]
    
    total_time = 0
    successful_requests = 0
    
    for test_name, question in test_cases:
        print(f"\n🧪 {test_name}")
        
        result = send_chat_request(question)
        
        if result["success"]:
            response_time = result['response_time_ms']
            total_time += response_time
            successful_requests += 1
            
            print(f"⏱️ Response time: {response_time}ms")
            print(f"📝 Response length: {len(result['response'])} characters")
            
            # Performance rating
            if response_time < 2000:
                print("🟢 Performance: Excellent")
            elif response_time < 5000:
                print("🟡 Performance: Good")
            else:
                print("🔴 Performance: Needs improvement")
        else:
            print(f"❌ Error: {result['error']}")
    
    if successful_requests > 0:
        avg_time = total_time / successful_requests
        print(f"\n📊 Average response time: {avg_time:.0f}ms")
        print(f"📊 Success rate: {successful_requests}/{len(test_cases)}")

def main():
    """Main testing function"""
    
    print("🧪 LM Studio API Testing Tool")
    print("="*50)
    print(f"📅 Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔗 Testing URL: {LM_STUDIO_URL}")
    print(f"🤖 Model: {MODEL_NAME}")
    
    # Test connection
    if not test_connection():
        print("\n❌ Cannot proceed without LM Studio connection")
        print("📋 Troubleshooting steps:")
        print("   1. Make sure LM Studio is running")
        print("   2. Load the mistral-nemo-instruct-2407 model")
        print("   3. Start the local server")
        print("   4. Check if port 1234 is available")
        return
    
    # Run all tests
    try:
        test_relevance_checking()
        test_document_analysis()
        test_unnes_questions()
        test_irrelevant_questions()
        performance_benchmark()
        
        print(f"\n🎉 Testing completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*50)
        
    except KeyboardInterrupt:
        print(f"\n⏸️ Testing interrupted by user")
    except Exception as e:
        print(f"\n❌ Testing failed with error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Interactive mode for custom testing
        question = " ".join(sys.argv[1:])
        print(f"🔍 Testing custom question: {question}")
        
        if not test_connection():
            exit(1)
        
        result = send_chat_request(question)
        
        if result["success"]:
            print(f"\n✅ Response:")
            print(result['response'])
            print(f"\n⏱️ Response time: {result['response_time_ms']}ms")
        else:
            print(f"\n❌ Error: {result['error']}")
    else:
        # Run full test suite
        main()