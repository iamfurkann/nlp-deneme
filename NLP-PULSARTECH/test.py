# chat_client.py

import requests
import json
import time

# --- Konfigürasyon ---
# Çalışan ana uygulamanın adresi
APP_URL = "http://127.0.0.1:8003/ask_intelligent"

def start_chat_session():
    """
    Kullanıcı ile interaktif bir sohbet oturumu başlatır.
    """
    print("--- RAG Asistan Chatbot Test Arayüzü ---")
    print("Merhaba! Ben Rehber Asistan. Sana nasıl yardımcı olabilirim?")
    print('("çıkış" yazarak oturumu sonlandırabilirsiniz.)')
    print("-" * 40)

    while True:
        try:
            user_query = input("Siz: ")
            
            if user_query.lower() in ["çıkış", "cikis", "quit", "exit"]:
                print("\nRehber Asistan: Görüşmek üzere! Hoşça kal.")
                break

            if not user_query.strip():
                continue

            payload = {"query": user_query}
            start_time = time.time()
            
            print("Rehber Asistan düşünüyor...")

            # Servise POST isteği gönder
            response = requests.post(APP_URL, json=payload, timeout=300) # 5 dakika timeout
            
            end_time = time.time()
            duration = end_time - start_time
            
            print("\n" + "="*50)

            if response.status_code == 200:
                result = response.json()
                
                print(f"Rehber Asistan ({duration:.2f} saniyede cevapladı):")
                print(result.get("answer", "Bir hata oluştu, cevap alınamadı."))
                
                sources = result.get("sources_used", [])
                if sources:
                    print("\n--- Kullanılan Kaynaklar ---")
                    for i, source in enumerate(sources, 1):
                        print(f"[{i}] {source}")
                
            else:
                print(f"HATA: Sunucudan {response.status_code} koduyla hata alındı.")
                print("Hata Detayı:", response.text)

            print("="*50 + "\n")

        except requests.exceptions.ConnectionError:
            print("\n[HATA] BAĞLANTI KURULAMADI.")
            print("Lütfen 'uvicorn main_app:app --reload' komutuyla ana uygulamanın çalıştığından emin olun.")
            break
        except requests.exceptions.ReadTimeout:
            print("\n[HATA] ZAMAN AŞIMI.")
            print("Sunucunun cevap vermesi çok uzun sürdü. Lütfen terminal loglarını kontrol edin.")
        except Exception as e:
            print(f"\n[BEKLENMEDİK HATA]: {e}")
            break

if __name__ == "__main__":
    start_chat_session()