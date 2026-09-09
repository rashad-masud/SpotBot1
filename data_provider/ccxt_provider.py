# data_provider/ccxt_provider.py

import ccxt
import time
import logging
from typing import Dict, Any, List, Optional
import threading
from dataclasses import dataclass

@dataclass
class MarketData:
    """Data class for market data"""
    pair: str
    price: float
    timestamp: float
    volume: float
    bid: float
    ask: float
    high: float
    low: float
    change: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            'pair': self.pair,
            'price': self.price,
            'timestamp': self.timestamp,
            'volume': self.volume,
            'bid': self.bid,
            'ask': self.ask,
            'high': self.high,
            'low': self.low,
            'change': self.change
        }

# Initialize logger for signal engine
logger = logging.getLogger(__name__)

class CCXTPprovider:
    """
    CCXT-based market data provider for Binance
    Compatible with the existing trading bot interface
    """

    def __init__(self, trading_pairs: List[str], cache_timeout: float = 0.5, max_retries: int = 3):
        """
        Initialize data provider for specific trading pairs
        
        Args:
            trading_pairs: List of trading pairs (e.g., ['ETH/USDT', 'XRP/USDT'])
            cache_timeout: Seconds to cache data
            max_retries: Maximum retry attempts for failed requests
        """
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Store trading pairs
        self.trading_pairs = trading_pairs
        self.logger.info(f"Initializing CCXT provider for pairs: {trading_pairs}")
        
        # Initialize CCXT Binance exchange
        self.exchange = ccxt.binance({
            'rateLimit': 1200,
            'enableRateLimit': True,
            'timeout': 10000,
            'options': {
                'defaultType': 'spot',
                'adjustForTimeDifference': True
            }
        })
        
        # Data caching
        self.cache_timeout = cache_timeout
        self.data_cache: Dict[str, MarketData] = {}
        self.cache_timestamps: Dict[str, float] = {}
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests
        
        # Retry configuration
        self.max_retries = max_retries
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'errors': 0,
            'last_update': None
        }
        
        # Thread lock for thread safety
        self._lock = threading.RLock()
        
        # Initialize markets and validate pairs
        self.validated_pairs = []
        self.binance_symbols = {}
        self._load_markets()
        
        # Test connection on initialization
        self._test_connection()
    
    def _load_markets(self):
        """Load markets and validate trading pairs using CCXT symbols"""
        try:
            self.logger.info("Loading Binance markets...")
            markets = self.exchange.load_markets()

            for pair in self.trading_pairs:
                if pair in markets:
                    market = markets[pair]
                    if market.get("active", True):
                        self.validated_pairs.append(pair)
                        self.binance_symbols[pair] = pair  # CCXT symbol
                        self.logger.info(f"✓ Pair validated: {pair}")
                    else:
                        self.logger.warning(
                            f"Pair {pair} exists but is not active on Binance"
                        )
                else:
                    self.logger.warning(f"Pair {pair} not found on Binance")

        except Exception as e:
            self.logger.error(f"Failed to load markets: {e}")
            raise

    
    def _test_connection(self):
        """Test connection to Binance API"""
        self.logger.info(f"CCXT data provider initialized for {len(self.validated_pairs)} pairs")
        
        if not self.validated_pairs:
            self.logger.warning("No validated trading pairs available")
            return
        
        # Test with first pair
        test_pair = self.validated_pairs[0]
        try:
            self._rate_limit()
            ticker = self.exchange.fetch_ticker(self.binance_symbols[test_pair])
            self.logger.info(f"✓ Binance connection successful - {test_pair}: ${ticker['last']:.2f}")
        except Exception as e:
            self.logger.error(f"✗ Binance connection failed: {e}")
    
    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _fetch_single_ticker(self, pair: str) -> Optional[MarketData]:
        """Fetch ticker data for a single pair with retry logic"""
        binance_symbol = self.binance_symbols.get(pair)
        
        if not binance_symbol:
            self.logger.warning(f"Invalid pair: {pair}")
            return None
        
        for attempt in range(self.max_retries):
            try:
                self._rate_limit()
                ticker = self.exchange.fetch_ticker(binance_symbol)
                self.stats['total_requests'] += 1

                self.logger.debug(
                    "[BINANCE] Data received from Binance | pair=%s price=%.6f",
                    pair,
                    ticker.get("last") or ticker.get("close", 0)
                )
                
                return MarketData(
                    pair=pair,
                    price=float(ticker['last'] if ticker['last'] else ticker['close']),
                    timestamp=ticker['timestamp'] / 1000.0,
                    volume=float(ticker['quoteVolume']),
                    bid=float(ticker['bid']),
                    ask=float(ticker['ask']),
                    high=float(ticker['high']),
                    low=float(ticker['low']),
                    change=float(ticker.get('percentage', 0.0))
                )
                
            except ccxt.BadSymbol:
                self.logger.error(f"Symbol error for {pair}: Not found on Binance")
                # Try to reload markets in case of symbol issues
                if attempt == 0:
                    try:
                        self.exchange.load_markets(reload=True)
                    except:
                        pass
                break
            except ccxt.NetworkError as e:
                if attempt == self.max_retries - 1:
                    self.logger.error(f"Network error for {pair} after {self.max_retries} attempts: {e}")
                    self.stats['errors'] += 1
                    break
                self.logger.warning(f"Network error for {pair} (attempt {attempt + 1}/{self.max_retries}): {e}")
                time.sleep(1 * (attempt + 1))
            except ccxt.ExchangeError as e:
                self.logger.error(f"Exchange error for {pair}: {e}")
                self.stats['errors'] += 1
                break
            except Exception as e:
                self.logger.error(f"Unexpected error for {pair}: {e}")
                self.stats['errors'] += 1
                break
        
        return None
    
    def get_all_market_data(self) -> Dict[str, MarketData]:
        """
        Get market data for all configured trading pairs
        
        Returns:
            Dictionary with pair -> MarketData
        """
        results = {}
        
        for pair in self.validated_pairs:
            # Check cache first
            cached_data = self._get_from_cache(pair)
            if cached_data:
                results[pair] = cached_data
                continue
            
            # Fetch from API
            market_data = self._fetch_single_ticker(pair)
            if market_data:
                self._update_cache(pair, market_data)
                results[pair] = market_data
        
        self.stats['last_update'] = time.time()
        return results
    
    def get_context(self, pair: str) -> Dict[str, Any]:
        """
        Get market context for a specific pair (compatible with MockDataProvider)
        
        Args:
            pair: Trading pair
            
        Returns:
            Dictionary with market data
        """
        # Check if pair is in our configured list
        if pair not in self.validated_pairs:
            # If not in validated pairs, try to fetch anyway (might be a new pair)
            self.logger.debug(f"Requested pair {pair} not in pre-validated pairs, attempting to fetch...")
            
            # Try to get the Binance symbol
            binance_symbol = pair.replace('/', '')
        if pair not in self.exchange.markets:
            self.logger.warning(f"Pair {pair} not found on Binance")
            return self._get_empty_context(pair)

        self.validated_pairs.append(pair)
        self.binance_symbols[pair] = pair
        
        # Check cache first
        cached_data = self._get_from_cache(pair)
        if cached_data:
            return cached_data.to_dict()
        
        # Fetch from API
        market_data = self._fetch_single_ticker(pair)
        if market_data:
            self._update_cache(pair, market_data)
            return market_data.to_dict()
        
        # Return empty context if fetch failed
        return self._get_empty_context(pair)
    
    def _get_from_cache(self, pair: str) -> Optional[MarketData]:
        """Get data from cache if fresh enough"""
        with self._lock:
            if pair in self.cache_timestamps:
                cache_age = time.time() - self.cache_timestamps[pair]
                if cache_age < self.cache_timeout:
                    self.stats['cache_hits'] += 1
                    return self.data_cache[pair]
        return None
    
    def _update_cache(self, pair: str, data: MarketData):
        """Update cache with new data"""
        with self._lock:
            self.data_cache[pair] = data
            self.cache_timestamps[pair] = time.time()
    
    def _get_empty_context(self, pair: str) -> Dict[str, Any]:
        """Return empty context for failed requests"""
        return {
            'pair': pair,
            'price': 0.0,
            'timestamp': time.time(),
            'volume': 0.0,
            'bid': 0.0,
            'ask': 0.0,
            'high': 0.0,
            'low': 0.0,
            'change': 0.0
        }
    
    def get_available_pairs(self) -> List[str]:
        """Get list of configured and validated pairs"""
        return self.validated_pairs.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get provider statistics"""
        with self._lock:
            total_requests = max(self.stats['total_requests'], 1)
            return {
                'configured_pairs': len(self.trading_pairs),
                'validated_pairs': len(self.validated_pairs),
                'total_requests': self.stats['total_requests'],
                'cache_hits': self.stats['cache_hits'],
                'cache_hit_rate': self.stats['cache_hits'] / total_requests,
                'errors': self.stats['errors'],
                'last_update': self.stats['last_update'],
                'cache_size': len(self.data_cache)
            }