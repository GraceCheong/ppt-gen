"""Rate limiting — slowapi 기반, IP별 제한."""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
