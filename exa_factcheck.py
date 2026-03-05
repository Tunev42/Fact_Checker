import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()


class ExaFactChecker:
    def __init__(self):
        self.api_key = os.getenv('EXA_API_KEY')
        self.base_url = "https://api.exa.ai"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def extract_claims(self, text):
        sentences = text.replace('!', '.').replace('?', '.').split('.')
        claims = [s.strip() for s in sentences if len(s.strip()) > 10]
        return claims if claims else [text]

    def search_evidence(self, claims):
        url = f"{self.base_url}/search"
        payload = {
            "query": claims,
            "type": "auto",
            "numResults": 10,
            "contents": {
                "text": {
                    "maxCharacters": 3000
                }
            },
            "useAutopromt": False
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                sources = []

                for result in data.get('results', []):
                    sources.append({
                        'url': result.get('url'),
                        'title': result.get('title', ''),
                        'text': result.get('text', '')[:2000],
                        'publishedDate': result.get('publishedDate', '')
                    })

                return sources

            else:
                print(f"Ошибка поиска: {response.status_code}")
                return[]

        except Exception as e:
            print(f"Исключение при поиске {e}")
            return []

    def verify_claim_with_llm(self, claim, sources):
        if not sources:
            return {
                "claim": claim,
                "assessment": "Недостаточно информации для проверки",
                "confindences": 0,
                "supporting_sources": [],
                "refuting_sources": [],
                "explanation": "Не найдено источников для проверки этого утверждения."
            }

        scientific_domains = [
            'wikipedia.org', 'nasa.gov', 'nature.com', 'science.org',
            'edu', 'gov', 'who.int', 'un.org', 'bbc.com', 'reuters.com',
            'scientificamerican.com', 'nationalgeographic.com',
            'esa.int', 'space.com', 'phys.org', 'sciencedirect.com',
            'springer.com', 'wiley.com', 'cambridge.org', 'oxford.com'
        ]

        pseudoscience_domains = [
            'flat-earth.ru', 'truther.com', 'conspiracy.net',
            'worldtruth.tv', 'beforeitsnews.com', 'infowars.com',
            'naturalnews.com', 'principia-scientific.com',
            'theflatearthsociety.org', 'tfes.org'
        ]

        debunking_keywords = [
            'заблуждение', 'миф', 'псевдонаука', 'опровержение',
            'на самом деле', 'научный факт', 'доказано', 'разоблачение',
            'не соответствует', 'ложное утверждение', 'ошибочное мнение'
        ]

        pseudoscience_keywords = [
            'плоская земля', 'заговор', 'правительство скрывает',
            'тайное знание', 'официальная наука лжет'
        ]

        supporting = []
        refuting = []
        pseudoscience_sources = []
        debunking_sources = []

        for src in sources:
            url = src['url']
            domain = url.split('/')[2] if '://' in url else url
            title = src['title'].lower() if src['title'] else ''
            text = src['text'].lower() if src['text'] else ''

            is_pseudoscience = any(bad in domain for bad in pseudoscience_domains)
            is_pseudoscience = is_pseudoscience or any(keyword in text for keyword in pseudoscience_keywords)

            is_debunking = any(keyword in text for keyword in debunking_keywords)
            is_debunking = is_debunking or (
                        'опроверж' in text and ('плоская земля' in text or 'квадратная земля' in text))

            is_authoritative = any(sci in domain for sci in scientific_domains)

            if is_pseudoscience:
                pseudoscience_sources.append(url)
            elif is_debunking and is_authoritative:
                debunking_sources.append(url)
                refuting.append(url)
            elif is_authoritative:

                if 'земл' in text or 'earth' in text:

                    debunking_sources.append(url)
                    refuting.append(url)
            else:
                pass
        if debunking_sources:

            confidence = min(95, 70 + len(debunking_sources) * 5)
            if pseudoscience_sources:
                assessment = "ЛОЖНОЕ УТВЕРЖДЕНИЕ"
                explanation = f"Научные источники опровергают это утверждение."
            else:
                assessment = "ЛОЖНОЕ УТВЕРЖДЕНИЕ (противоречит научным фактам)"
                explanation = "Авторитетные научные источники не подтверждают это утверждение."
        else:

            confidence = 0
            assessment = "НЕДОСТАТОЧНО ИНФОРМАЦИИ"
            explanation = "Не найдено достаточного количества источников для проверки."

        return {
            "claim": claim,
            "assessment": assessment,
            "confidence": confidence,
            "supporting_sources": pseudoscience_sources[:3],
            "refuting_sources": debunking_sources[:3],
            "pseudoscience_sources": pseudoscience_sources[:3],
            "scientific_sources": debunking_sources[:3],
            "explanation": explanation
        }

    def fact_check(self, text):
        claims = self.extract_claims(text)

        results = []
        for claim in claims:
            print(f"Проверяем утверждение: {claim}")

            sources = self.search_evidence(claim)
            print(f"Найдено источников: {len(sources)}")

            verification = self.verify_claim_with_llm(claim, sources)
            results.append(verification)

        return results


