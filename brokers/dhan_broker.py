"""
Dhan Broker module for handling all API interactions
"""

import os
import time
import json
import requests
from utils.rate_limiter import make_rate_limited_request, add_delay_between_requests
from utils.market_utils import round_to_tick

class DhanBroker:
    """Dhan broker for order management and API interactions"""
    
    def __init__(self, client_id, access_token, tick_size=0.05):
        self.client_id = client_id
        self.access_token = access_token
        self.tick_size = tick_size
        self.base_url = "https://api.dhan.co/v2/super"
    
    def get_security_id(self, symbol, instruments_df):
        """Get Security ID for a given symbol"""
        try:
            if instruments_df is None:
                return None
            
            # Filter for options in NSE
            options_df = instruments_df[
                (instruments_df['EXCH_ID'] == 'NSE') & 
                (instruments_df['SEGMENT'] == 'D') &
                (instruments_df['INSTRUMENT'] == 'OPTIDX')
            ]
            
            # Find the exact matching symbol using DISPLAY_NAME
            matching_instrument = options_df[options_df['DISPLAY_NAME'] == symbol]
            
            if not matching_instrument.empty:
                security_id = int(matching_instrument.iloc[0]['SECURITY_ID'])
                return security_id
            else:
                print(f"No matching instrument found for symbol {symbol}")
                return None
                
        except Exception as e:
            print(f"Error getting security ID: {e}")
            return None
    
    def get_account_balance(self) -> float:
        """Get current account balance from Dhan API using /v2/fundlimit endpoint"""
        try:
            headers = {
                'access-token': self.access_token,
                'Content-Type': 'application/json'
            }
            
            # CORRECTED: Use the correct full URL for fundlimit endpoint with rate limiting
            response = make_rate_limited_request(
                'GET',
                'https://api.dhan.co/v2/fundlimit',
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"Account balance response: {json.dumps(data, indent=2)}")
                
                # Extract available balance from fundlimit response
                if 'availabelBalance' in data:
                    return float(data['availabelBalance'])
                else:
                    print("Could not find availabelBalance in API response")
                    print(f"Available fields: {list(data.keys())}")
                    return 0.0
            else:
                print(f"Failed to get account balance: {response.status_code}")
                print(f"Response: {response.text}")
                return 0.0
                
        except Exception as e:
            print(f"Error getting account balance: {e}")
            return 0.0
    
    def place_order(self, symbol, quantity, order_type="MARKET", side="BUY", 
                   price=0, target_price=None, stop_loss_price=None, trailing_jump=None, instruments_df=None):
        """Place an order using Dhan API"""
        try:
            # Get the security ID for the symbol
            security_id = self.get_security_id(symbol, instruments_df)
            if not security_id:
                print(f"Could not find security ID for symbol {symbol}")
                return None

            # Generate correlation ID
            correlation_id = f"order_{int(time.time())}_{int(time.time() * 1000) % 1000}"
            
            # Prepare order payload - CORRECTED to match Dhan API format
            order_payload = {
                "dhanClientId": self.client_id,
                "correlationId": correlation_id,
                "transactionType": side,
                "exchangeSegment": "NSE_FNO",
                "productType": "INTRADAY",
                "orderType": order_type,
                "securityId": str(security_id),
                "quantity": int(quantity)
            }
            
            # Add optional parameters with price rounding
            if target_price:
                order_payload["targetPrice"] = round_to_tick(target_price, self.tick_size)
            if stop_loss_price:
                order_payload["stopLossPrice"] = round_to_tick(stop_loss_price, self.tick_size)
            if price > 0:
                order_payload["price"] = round_to_tick(price, self.tick_size)
            
            print("Placing order with parameters:")
            print(json.dumps(order_payload, indent=2))
            
            # Make API call
            headers = {
                'access-token': self.access_token,
                'Content-Type': 'application/json'
            }
            
            # Use rate-limited request to avoid hitting API limits
            response = make_rate_limited_request(
                'POST',
                f'{self.base_url}/orders',
                headers=headers,
                json=order_payload
            )
            
            if response.status_code == 200:
                order_response = response.json()
                print(f"Order placed successfully: {json.dumps(order_response, indent=2)}")
                
                # Check for orderId in response (correct Dhan API format)
                if 'orderId' in order_response:
                    return order_response
                else:
                    print(f"Order placement failed - no orderId in response: {order_response}")
                    return None
            else:
                print(f"API call failed with status code: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error placing order: {e}")
            return None

    def modify_target(self, order_id, target_price):
        """Modify target price for an existing order"""
        try:
            # Round target price to tick size
            rounded_target = round_to_tick(target_price, self.tick_size)
            
            # Prepare modification payload - CORRECTED to match Dhan API format
            modify_payload = {
                "dhanClientId": self.client_id,
                "orderId": order_id,
                "legName": "TARGET_LEG",
                "targetPrice": rounded_target
            }
            
            print("Modifying target with parameters:")
            print(json.dumps(modify_payload, indent=2))
            
            # Make API call
            headers = {
                'access-token': self.access_token,
                'Content-Type': 'application/json'
            }
            
            response = requests.put(
                f'{self.base_url}/orders/{order_id}',
                headers=headers,
                json=modify_payload
            )
            
            if response.status_code == 200:
                modify_response = response.json()
                print(f"Target modified successfully: {json.dumps(modify_response, indent=2)}")
                return modify_response
            else:
                print(f"API call failed with status code: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error modifying target: {e}")
            return None

    def modify_stop_loss(self, order_id, stop_loss_price):
        """Modify stop loss price for an existing order"""
        try:
            # Round stop loss price to tick size
            rounded_sl = round_to_tick(stop_loss_price, self.tick_size)
            
            # Prepare modification payload - CORRECTED to match Dhan API format
            modify_payload = {
                "dhanClientId": self.client_id,
                "orderId": order_id,
                "legName": "STOP_LOSS_LEG",
                "stopLossPrice": rounded_sl
            }
            
            print("Modifying stop loss with parameters:")
            print(json.dumps(modify_payload, indent=2))
            
            # Make API call
            headers = {
                'access-token': self.access_token,
                'Content-Type': 'application/json'
            }
            
            response = requests.put(
                f'{self.base_url}/orders/{order_id}',
                headers=headers,
                json=modify_payload
            )
            
            if response.status_code == 200:
                modify_response = response.json()
                print(f"Stop loss modified successfully: {json.dumps(modify_response, indent=2)}")
                return modify_response
            else:
                print(f"API call failed with status code: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error modifying stop loss: {e}")
            return None

    def cancel_order(self, order_id, order_leg="ENTRY_LEG"):
        """Cancel an active order using Dhan API"""
        try:
            print(f"Cancelling order: {order_id} (leg: {order_leg})")
            
            # Make API call - CORRECTED to match Dhan API format
            headers = {
                'access-token': self.access_token,
                'Content-Type': 'application/json'
            }
            
            # CORRECTED: Use the proper endpoint with order-id and order-leg
            response = requests.delete(
                f'{self.base_url}/orders/{order_id}/{order_leg}',
                headers=headers
            )
            
            # CORRECTED: Expect 202 Accepted status code
            if response.status_code == 202:
                cancel_response = response.json()
                print(f"Order cancelled successfully: {json.dumps(cancel_response, indent=2)}")
                return cancel_response
            else:
                print(f"API call failed with status code: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error cancelling order: {e}")
            return None

    def cancel_target_leg(self, order_id):
        """Cancel the target leg of an order"""
        return self.cancel_order(order_id, "TARGET_LEG")
    
    def cancel_stop_loss_leg(self, order_id):
        """Cancel the stop loss leg of an order"""
        return self.cancel_order(order_id, "STOP_LOSS_LEG")
    
    def cancel_entry_leg(self, order_id):
        """Cancel the main entry leg of an order (cancels all legs)"""
        return self.cancel_order(order_id, "ENTRY_LEG")
    
    def get_positions(self):
        """Get current positions from Dhan API"""
        try:
            headers = {
                'access-token': self.access_token,
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f'{self.base_url}/positions',
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                positions = {}
                
                # Parse positions from API response
                if 'data' in data and 'positions' in data['data']:
                    for position in data['data']['positions']:
                        symbol = position.get('symbol', 'Unknown')
                        quantity = position.get('quantity', 0)
                        if quantity != 0:  # Only include non-zero positions
                            positions[symbol] = {
                                'quantity': quantity,
                                'avg_price': position.get('avgPrice', 0),
                                'pnl': position.get('pnl', 0),
                                'side': position.get('side', 'UNKNOWN')
                            }
                
                return positions
            else:
                print(f"Failed to get positions: {response.status_code}")
                return {}
                
        except Exception as e:
            print(f"Error getting positions: {e}")
            return {}
    
    def get_order_status(self, order_id):
        """Get order status from Dhan API"""
        try:
            headers = {
                'access-token': self.access_token,
                'Content-Type': 'application/json'
            }
            
            # CORRECTED: Use the correct endpoint format
            response = requests.get(
                f'{self.base_url}/orders/{order_id}',
                headers=headers
            )
            
            if response.status_code == 200:
                order_data = response.json()
                print(f"Order status retrieved: {json.dumps(order_data, indent=2)}")
                return order_data
            else:
                print(f"Failed to get order status: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error getting order status: {e}")
            return None
    
    def print_account_summary(self):
        """Print account summary for live trading"""
        try:
            # Get account balance
            balance = self.get_account_balance()
            print(f"\n💰 Account Balance: ₹{balance:,.2f}")
            
            # Get positions
            positions = self.get_positions()
            if positions:
                print(f"📊 Active Positions: {len(positions)}")
                for symbol, pos in positions.items():
                    print(f"   {symbol}: {pos['quantity']} qty @ ₹{pos['avg_price']:.2f} (P&L: ₹{pos['pnl']:.2f})")
            else:
                print("📊 No active positions")
                
        except Exception as e:
            print(f"Error printing account summary: {e}")
