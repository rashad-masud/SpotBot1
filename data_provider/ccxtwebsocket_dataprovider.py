import asyncio
import websockets
import json
from typing import Callable, Dict, Any

class CCXTWebSocketDataProvider:
    """WebSocket-based real-time data from Binance"""
    
    def __init__(self, pairs: List[str]):
        self.pairs = pairs
        self.current_prices: Dict[str, float] = {}
        self.callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self.running = False
        
    async def connect(self):
        """Connect to Binance WebSocket"""
        streams = [f"{pair.lower().replace('/', '')}@ticker" for pair in self.pairs]
        stream_url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"
        
        async with websockets.connect(stream_url) as websocket:
            self.running = True
            print(f"Connected to Binance WebSocket for {len(self.pairs)} pairs")
            
            while self.running:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    # Parse ticker data
                    stream_data = data.get('data', {})
                    symbol = stream_data.get('s', '')
                    
                    if symbol:
                        # Convert symbol back to pair format (ETHUSDT -> ETH/USDT)
                        pair = f"{symbol[:-4]}/{symbol[-4:]}"
                        
                        ticker_data = {
                            'pair': pair,
                            'price': float(stream_data.get('c', 0)),
                            'timestamp': stream_data.get('E', 0) / 1000,
                            'volume': float(stream_data.get('q', 0)),
                            'bid': float(stream_data.get('b', 0)),
                            'ask': float(stream_data.get('a', 0)),
                            'high': float(stream_data.get('h', 0)),
                            'low': float(stream_data.get('l', 0)),
                            'change': float(stream_data.get('P', 0))
                        }
                        
                        # Update current price
                        self.current_prices[pair] = ticker_data['price']
                        
                        # Notify callbacks
                        for callback in self.callbacks:
                            callback(ticker_data)
                            
                except Exception as e:
                    print(f"WebSocket error: {e}")
                    await asyncio.sleep(1)
    
    def get_context(self, pair: str) -> Dict[str, Any]:
        """Get latest data from WebSocket (non-blocking)"""
        price = self.current_prices.get(pair, 0.0)
        
        return {
            'pair': pair,
            'price': price,
            'timestamp': time.time(),
            'volume': 0.0,  # Would need to track this separately
            'bid': price * 0.999,
            'ask': price * 1.001,
            'high': price,
            'low': price,
            'change': 0.0
        }