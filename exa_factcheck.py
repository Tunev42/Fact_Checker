import os
import re
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    text: str
    verdict: str
    confidence: int
    explanation: Optional[str] = None
    sources: List[str] = field(default_factory=list)
    supporting: List[str] = field(default_factory=list)
    refuting: List[str] = field(default_factory=list)


class FactVerifier:
    AUTHORITATIVE_DOMAINS: Set[str] = {
        'wikipedia.org', 'nasa.gov', 'nature.com', 'science.org',
        '.edu', '.gov', 'who.int', 'un.org', 'reuters.com',
        'scientificamerican.com', 'nationalgeographic.com',
        'esa.int', 'phys.org', 'sciencedirect.com', 'springer.com',
        'cambridge.org', 'oxford.com', 'scholar.google.com',
        'pubmed.ncbi.nlm.nih.gov', 'arxiv.org',
        'elementy.ru', 'postnauka.ru', 'nkj.ru',  'ras.ru', 'cyberleninka.ru', 'istina.msu.ru',
    }

    UNRELIABLE_DOMAINS: Set[str] = {
        'flat-earth.ru', 'truther.com', 'infowars.com',
        'naturalnews.com', 'theflatearthsociety.org'
    }

    DEBUNKING_PATTERNS: List[str] = [
        r'заблуждени[ея]', r'миф|мифы', r'псевдонаук[аи]',
        r'опровержени[ея]', r'разоблачени[ея]',
        r'не соответствует действительности',
        r'научн[ыу]х? факт[а-я]*',
        r'доказан[оы]',
    ]

    def __init__(self, api_key: Optional[str] = None, timeout: int = 15):
        self.api_key = api_key or os.getenv('EXA_API_KEY')
        if not self.api_key:
            raise ValueError('API ключ не предоставлен')

        self.base_url = "https://api.exa.ai"
        self.timeout = timeout

        self.session = self._create_http_session()

        self.debunking_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.DEBUNKING_PATTERNS
        ]

    def _create_http_session(self) -> requests.Session:
        session = requests.Session()

        retry_strategy = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )

        session.mount('http://', adapter)
        session.mount('https://', adapter)

        session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "FactChecker/1.0"
        })

        return session

    def check(self, text: str) -> Dict:
        if not text or len(text) < 10:
            raise ValueError('Текст слишком короткий для проверки')

        claims = self._extract_claims(text)

        results = []
        for claim in claims:
            try:
                result = self._verify_claim(claim)
                results.append(result)
            except Exception as e:
                logger.error(f"Ошибка при проверке утверждения '{claim[:50]}...': {str(e)}")
                results.append(VerificationResult(
                    text=claim,
                    verdict='ОШИБКА ПРОВЕРКИ',
                    confidence=0,
                    explanation='Техническая ошибка при проверке'
                ))

        return {
            'original': text,
            'claims_count': len(results),
            'claims': [self._result_to_dict(r) for r in results]
        }

    def _extract_claims(self, text: str) -> List[str]:

        text = re.sub(r'[.!?]+', '.', text)

        sentences = [s.strip() for s in text.split('.') if s.strip()]

        claims = [s for s in sentences if len(s) > 15]

        return claims if claims else [text]

    def _verify_claim(self, claim: str) -> VerificationResult:

        sources = self._search_sources(claim)

        if not sources:
            return VerificationResult(
                text=claim,
                verdict='НЕДОСТАТОЧНО ДАННЫХ',
                confidence=0,
                explanation='Не найдено источников для проверки'
            )

        scientific, unreliable, debunking = self._classify_sources(sources)

        if debunking:
            confidence = min(95, 70 + len(debunking) * 5)
            verdict = 'ЛОЖНОЕ УТВЕРЖДЕНИЕ'
            explanation = 'Авторитетные источники опровергают данное утверждение'
            sources_list = debunking
        elif scientific and not unreliable:
            confidence = 80
            verdict = 'ВЕРОЯТНО ИСТИННО'
            explanation = 'Утверждение подтверждается научными источниками'
            sources_list = scientific
        else:
            confidence = 30
            verdict = 'ТРЕБУЕТСЯ ПРОВЕРКА'
            explanation = 'Найдены противоречивые или ненадежные источники'
            sources_list = []

        return VerificationResult(
            text=claim,
            verdict=verdict,
            confidence=confidence,
            explanation=explanation,
            sources=sources_list[:5],
            supporting=scientific[:3],
            refuting=debunking[:3]
        )

    def _search_sources(self, query: str) -> List[Dict]:
        url = f"{self.base_url}/search"

        payload = {
            "query": query,
            "numResults": 20,
            "contents": {"text": {"maxCharacters": 2000}},
            "useAutoprompt": False
        }

        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code != 200:
                logger.warning(f"Поиск вернул код {response.status_code}")
                return []

            data = response.json()

            sources = []
            for item in data.get('results', []):
                sources.append({
                    'url': item.get('url'),
                    'title': item.get('title', ''),
                    'text': item.get('text', '')[:1500],
                    'date': item.get('publishedDate', '')
                })

            return sources

        except requests.exceptions.Timeout:
            logger.error(f"Таймаут при поиске: {query[:50]}...")
            raise ConnectionError('Превышено время ожидания ответа')
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса: {str(e)}")
            return []

    def _classify_sources(self, sources: List[Dict]) -> Tuple[List[str], List[str], List[str]]:
        scientific = []
        unreliable = []
        debunking = []

        for src in sources:
            url = src['url']
            domain = self._extract_domain(url)
            text = src.get('text', '').lower()
            title = src.get('title', '').lower()

            if any(bad in domain for bad in self.UNRELIABLE_DOMAINS):
                unreliable.append(url)
                continue

            is_authoritative = any(
                auth in domain for auth in self.AUTHORITATIVE_DOMAINS
            )

            if is_authoritative:
                scientific.append(url)

                full_text = f"{title} {text}"
                if self._is_debunking_content(full_text):
                    debunking.append(url)

        return scientific, unreliable, debunking

    def _extract_domain(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except:
            return url.lower()

    def _is_debunking_content(self, text: str) -> bool:
        for pattern in self.debunking_patterns:
            if pattern.search(text):
                return True
        return False

    @staticmethod
    def _result_to_dict(result: VerificationResult) -> Dict:
        return {
            'text': result.text,
            'verdict': result.verdict,
            'confidence': result.confidence,
            'explanation': result.explanation,
            'sources': result.sources,
            'supporting': result.supporting,
            'refuting': result.refuting
        }

    def __del__(self):
        if hasattr(self, 'session'):
            self.session.close()
