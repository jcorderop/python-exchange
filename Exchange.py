
from flask import Flask, render_template, request
from flask_restful import Api, Resource
from flasgger import Swagger

import datetime

import BinanceApi
from Cache import PricesCache
from OptionModel import download_data_single, calculate_volatility, calculate_return_log
from OptionPriceMonteCarlo import OptionPricing

prices_cache = PricesCache()
BinanceApi.start_price_client(prices_cache)


class Exchange(Resource):

    def __init__(self):
        pass

    def get(self):
        """
        Retrieve Snapshot Crypto Currency Prices List
        ---
        responses:
          200:
            description: List of crypto prices
            schema:
              id: CurrencyPair
              properties:
                prices:
                  type: json
                  description: List of Currency Pair with prices
                timestamp:
                  type: string
                  description: snapshot timestamp
        """
        global prices_cache
        prices = {
            "prices": prices_cache.__cache__,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        return prices, 200


class OptionCalculation(Resource):

    def get(self, stock, expiry, opt_type):
        """
                    Option Equity Price Calculation
                    ---
                    parameters:
                      - in: path
                        name: stock
                        type: string
                        required: true
                      - in: path
                        name: expiry
                        type: integer
                        required: true
                      - in: path
                        name: opt_type
                        type: string
                        enum: ['call', 'put']
                        required: true
                    responses:
                      200:
                        description: Option Price
                        schema:
                          id: OptionPrice
                          properties:
                            stock:
                              type: string
                              description: Stock Name requested
                            expiry:
                              type: string
                              description: expiry in years
                            type:
                              type: string
                              description: Option type
                            option_price:
                              type: string
                              description: Option price calculated
                            stock_price:
                              type: string
                              description: Stock prices used as reference
                            strike:
                              type: string
                              description: Option strike (absolute)
                            strike_pct:
                              type: string
                              description: Option strike (in pct)
                    """
        print("New Option request...")
        print('Stock: {}, Expiry: {} Option Type: {}'.format(stock, expiry, opt_type))
        #args = request.args
        stock_name = stock#args.get('stock')

        try:
            expiry = self.get_expiry(expiry)
            option_type = self.get_option_type(opt_type)
            option_price, stock_price, strike, strike_pct = self.calculate_option(expiry, stock_name, option_type)

            price = {
                "stock": stock_name,
                "expiry": "{}y".format(expiry),
                "type": option_type,
                "option_price": "{0:.3f}".format(option_price),
                "stock_price": "{0:.3f}".format(stock_price),
                "strike": "{0:.3f}".format(strike),
                "strike_pct": "{0:.2f}".format(strike_pct)
            }

            print("Option calculated...")
            return price, 200
        except Exception as e:
            bad_request = {
                "error": str(e)
            }
            return bad_request, 400

    def get_option_type(self, option_type):
        #option_type = args.get('opt_type')
        valid_type = option_type in ["put", "call"]
        if not valid_type:
            raise Exception("Invalid type {}".format(valid_type))
        return option_type

    def get_expiry(self, expiry):
        #expiry = args.get('expiry')
        try:
            return float(expiry)
        except Exception as e:
            raise Exception("Invalid expiry {}, {}".format(expiry, e))

    def get_today(self):
        current_date = datetime.date.today()
        return current_date.strftime("%Y-%m-%d")

    def get_prices(self, stock_name):
        try:
            return download_data_single(stock_name, '2010-01-01', self.get_today())
        except:
            raise Exception("Invalid stock name, could not retrieve prices.")

    def get_stock_prices(self, prices):
        try:
            stock_price = float(prices.tail(1)['Close'])
            print("Stock price: ", stock_price)
            return stock_price
        except:
            raise Exception("Invalid stock name, could not retrieve stock price.")

    def calculate_option(self, expiry, stock_name, option_type):

        risk_free_rate = 0.006  # switzerland

        prices = self.get_prices(stock_name)
        stock_price = self.get_stock_prices(prices)

        strike = stock_price * 1
        strike_pct = 100 * 1
        print("Strike level {}: ".format(strike))
        print("Strike pct {}%: ".format(strike_pct))
        print("Expiry {}y: ".format(expiry))
        calculate_return_log(prices)
        volatility = calculate_volatility(prices)
        print("Volatility: ", volatility)
        model = OptionPricing(stock_price, strike, expiry, risk_free_rate, volatility, 1000)
        if option_type == 'call':
            option_price = model.call_option_simulation()
        else:
            option_price = model.put_option_simulation()
        return option_price, stock_price, strike, strike_pct


app = Flask(__name__)
api = Api(app)
SWAGGER_TEMPLATE = {"securityDefinitions": {"APIKeyHeader": {"type": "apiKey", "name": "x-access-token", "in": "header"}}}
swagger = Swagger(app, template=SWAGGER_TEMPLATE)
api.add_resource(Exchange, "/api/rest/prices")
api.add_resource(OptionCalculation, "/api/rest/option_prices/<stock>/<expiry>/<opt_type>")


@app.route('/')
def index():
    return render_template('index.html')



app.run(host="0.0.0.0", debug=True, use_reloader=False, port=80)

