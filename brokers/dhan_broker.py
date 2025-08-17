"""
Dhan Broker module for handling all API interactions
"""

import os
import time
import json
import requests
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
        """Get current account balance from Dhan API"""
        try:
            headers = {
                'access-token': self.access_token,
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f'{self.base_url}/holdings',
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                # Extract available balance from holdings response
                # This is a simplified implementation - adjust based on actual API response structure
                if 'data' in data and 'availableBalance' in data['data']:
                    return float(data['data']['availableBalance'])
                else:
                    print("Could not find balance in API response")
                    return 0.0
            else:
                print(f"Failed to get account balance: {response.status_code}")
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
            
            # Prepare order payload
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
            if trailing_jump:
                order_payload["trailingJump"] = int(trailing_jump)
            if price > 0:
                order_payload["price"] = round_to_tick(price, self.tick_size)
            
            print("Placing order with parameters:")
            print(json.dumps(order_payload, indent=2))
            
            # Make API call
            headers = {
                'access-token': self.access_token,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f'{self.base_url}/orders',
                headers=headers,
                json=order_payload
            )
            
            if response.status_code == 200:
                order_response = response.json()
                print(f"Order placed successfully: {json.dumps(order_response, indent=2)}")
                
                if order_response.get('orderStatus') == 'TRANSIT' or order_response.get('status') == 'success':
                    return order_response
                else:
                    print(f"Order placement failed: {order_response}")
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
            
            # Prepare modification payload
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

    def cancel_order(self, order_id):
        """Cancel an active order using Dhan API"""
        try:
            # Prepare cancellation payload
            cancel_payload = {
                "dhanClientId": self.client_id,
                "orderId": order_id
            }
            
            print(f"Cancelling order: {order_id}")
            
            # Make API call
            headers = {
                'access-token': self.access_token,
                'Content-Type': 'application/json'
            }
            
            response = requests.delete(
                f'{self.base_url}/orders/{order_id}',
                headers=headers,
                json=cancel_payload
            )
            
            if response.status_code == 200:
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
