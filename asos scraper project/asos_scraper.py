import os
import re
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import requests
import time


def extract_info_from_url(url):
    if not is_valid_asos_product_link(url):
        print("Not a valid ASOS link")
        return
    options = Options()
    options.headless = True
    options.add_argument('window-size=1920x1080')
    options.add_argument("--enable-logging")  # Enable browser logging
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    path = os.getenv('CHROMEDRIVER_PATH')

    driver = webdriver.Chrome(path, options=options)

    try:
        # Navigate to the URL
        driver.get(url)

        # Wait for the name element to be present on the page
        name_element = WebDriverWait(driver, 2).until(
            EC.visibility_of_element_located((By.CLASS_NAME, "jcdpl"))
        )

        # Extract the name text
        name_text = name_element.get_attribute("innerText").strip()
        print("Product Name:", name_text)

        try:
            price_element = WebDriverWait(driver, 1).until(
                EC.visibility_of_element_located(
                    (By.XPATH, "//span[@data-testid='current-price' and contains(@class, 'MwTOW BR6YF')]")
                )
            )
        except TimeoutException:
            # If the first attempt times out, try the second XPATH without 'BR6YF'
            price_element = WebDriverWait(driver, 1).until(
                EC.visibility_of_element_located(
                    (By.XPATH, "//span[@data-testid='current-price' and contains(@class, 'MwTOW')]")
                )
            )

        # Extract the price text
        price_text = price_element.get_attribute("innerText").strip()

        # Split the price_text into parts
        parts = price_text.split()

        if len(parts) == 3 and parts[0] == "Now":
            # Extract the price_number and price_currency
            price_number = float(parts[1])
            price_currency = parts[2]

            print("Price Number:", price_number)
            print("Price Currency:", price_currency)

        elif len(parts) == 2 and parts[0] != "Now":
            # Extract the price_number and price_currency
            price_number = float(parts[0])
            price_currency = parts[1]

            print("Price Number:", price_number)
            print("Price Currency:", price_currency)

        else:
            print("Unexpected price format.")

            # Return the extracted values
        return price_currency, name_text, price_number

    except TimeoutException as te:
        print(f"TimeoutException: {te}")
    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        # Close the WebDriver
        driver.quit()


def is_valid_asos_product_link(link):
    # Regular expression to match ASOS product links
    asos_link_pattern = re.compile(r'https://www\.asos\.com/.+/prd/\d+.*')

    # Check if the link matches the pattern
    return bool(asos_link_pattern.match(link))


def extract_asos_product_id(url):
    # Regular expression to extract the product ID from ASOS URLs
    pattern = re.compile(r'/prd/(\d+)')

    # Search for the pattern in the URL
    match = pattern.search(url)

    # Check if a match is found and return the product ID
    if match:
        return match.group(1)
    else:
        return None


def build_request_link(product_id):
    base_url = "https://codembo.com/en/prd/"
    currency_param = "?cur=EUR"
    return base_url + str(product_id) + currency_param


def asos_price_comparison(url):
    # Create an empty DataFrame
    df = pd.DataFrame(columns=[
        'product_id',
        'product_name',
        'product_price_SA',
        'product_price_IL',
        'product_price_HK',
        'product_price_CN',
        'product_price_AU',
        'product_price_SE',
        'product_price_UK'
    ])


def extract_info_codembo_url(url):
    try:
        # Throttling: Introduce a delay between requests to avoid rate limiting
        time.sleep(1)  # 1-second delay

        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses
    except requests.RequestException as e:
        print(f"Error fetching URL: {e}")
        return None, None

    try:
        soup = BeautifulSoup(response.text, 'html.parser')

        # Robust Selector for product_name
        product_name_element = soup.select_one('h1.prd-card-title')
        if product_name_element:
            product_name = product_name_element.text.strip()
        else:
            print("Product name not found.")
            return None, None

        product_prices = {}

        # Robust Selectors for country_code and price
        for row in soup.select('table.goodt tbody tr'):
            country_code_element = row.select_one('td')
            price_element = row.select_one('td:nth-of-type(2)')

            if country_code_element and price_element:
                country_code = country_code_element.text.strip()
                price = price_element.text.strip()
                product_prices[country_code] = price

        # Return the result
        return product_name, product_prices
    except Exception as e:
        print(f"Error parsing HTML: {e}")
        return None, None


def calculate_basket_total(products):
    # Initialize a dictionary to store total costs for each country
    total_costs = {}

    # Initialize a set to keep track of country codes with prices for all products
    valid_country_codes = set()

    # Initialize a dictionary to store country codes for each product
    product_country_codes = {}

    # Iterate through each product in the basket
    for product_name, product_prices in products:
        print(f"Product: {product_name}")
        print("Prices:")

        # Flag to check if the product has prices for all countries
        has_all_prices = True

        # Use the minimum set of country codes from the previous products, if available
        if valid_country_codes:
            current_country_codes = valid_country_codes
        else:
            current_country_codes = set(product_prices.keys())

        # Update the country codes for the current product
        product_country_codes[product_name] = current_country_codes

        for country_code in current_country_codes:
            price = product_prices.get(country_code, None)
            print(f"{country_code}: {price}")

            # Check if the price is missing for the current country
            if price is None:
                print(f"Missing price for {country_code} in {product_name}")
                has_all_prices = False
            else:
                # Convert price to float and accumulate total cost for the country
                price_float = float(price)
                total_costs.setdefault(country_code, 0)
                total_costs[country_code] += price_float

        print()

        # If the product is missing a price for any country, skip it
        if not has_all_prices:
            print(f"Skipping {product_name} due to missing prices for some countries.\n")
            continue

        # Add country codes with prices for the current product to the set
        valid_country_codes.update(current_country_codes)

    # Print the total costs for country codes with prices for all products
    print("Total Costs:")
    for country_code, total_cost in total_costs.items():
        if country_code in valid_country_codes:
            print(f"{country_code}: {total_cost:.2f}")


def calculate_basket_total_df(products):
    df = pd.DataFrame(columns=[
        'product_id',
        'product_name',
        'product_price_SA',
        'product_price_IL',
        'product_price_HK',
        'product_price_CN',
        'product_price_AU',
        'product_price_SE',
        'product_price_UK'
    ])
    for product_name, product_prices in products:
        df["product_name"] = product_name


def create_dataframe(products):
    data = []
    # Iterate through each product in the basket
    for product_name, product_prices in products:
        # Create a dictionary to store data for the current product
        product_data = {'product_name': product_name}

        # Add product prices to the dictionary
        product_data.update(product_prices)

        # Add availability columns for each country
        for country_code in product_prices.keys():
            availability_column_name = f'{country_code}_available'

            # Add availability columns for each country
            for country_code in product_prices.keys():
                availability_column_name = f'{country_code}_available'
                product_data[availability_column_name] = not pd.isnull(product_prices[country_code])
        # Append the product data to the list
        data.append(product_data)

    # Create a DataFrame from the list of product data
    df = pd.DataFrame(data)

    print(df.columns)
    df = df.fillna(False)
    sum_df = pd.DataFrame(index=['Sum'])
    for country_code in product_prices.keys():
        df[country_code] = pd.to_numeric(df[country_code],
                                         errors='coerce')  # Convert to numeric, handle errors by setting them to NaN
        sum_df[country_code] = df[country_code].sum()

    export_to_csv(sum_df, 'sum_output.csv')
    export_to_csv(df)

    return df, sum_df


def analyze_price_each_country(df, sum_df):
    # Flatten the sum_df DataFrame and sort it to find the two smallest values
    sorted_sum = sum_df.unstack().sort_values()

    # Extract the two smallest values and their corresponding countries
    smallest_values = sorted_sum.head(2)
    cheapest_country, second_cheapest_country = [col[0] for col in smallest_values.index]
    print(cheapest_country)
    print(second_cheapest_country)
    result_df, sum_basket = compare_prices(df, cheapest_country, second_cheapest_country)

    basket_dict = {}

    for index, row in result_df.iterrows():
        product_name = row['product_name']
        country = row['Country']
        price = row['Cheapest_Price']

        if country not in basket_dict:
            basket_dict[country] = {'products': [], 'total_price': 0}

        basket_dict[country]['products'].append({'product_name': product_name, 'price': price})
        basket_dict[country]['total_price'] += price

    # Print the basket_dict
    for country, details in basket_dict.items():
        print(f"Country: {country}")
        print("Products:")
        for product in details['products']:
            print(f"  - {product['product_name']}: {product['price']}")
        print(f"Total Price: {details['total_price']:.2f}")


def compare_prices(df, cheapest_country, second_cheapest_country):
    # Create an empty list to store the results
    result_list = []

    # Iterate through each product
    for index, row in df.iterrows():
        product_name = row['product_name']

        if row[cheapest_country] == 0.0 and row[second_cheapest_country] == 0.0:
            # Find minimum non-zero price and country
            non_zero_prices = {col: price for col, price in row.items() if price != 0}
            if non_zero_prices:
                cheapest_country = min(non_zero_prices, key=non_zero_prices.get)
                cheapest_price = non_zero_prices[cheapest_country]
            else:
                cheapest_country = None
                cheapest_price = 0.0
        else:
            cheapest_price = row[cheapest_country] if row[second_cheapest_country] == 0.0 else (
                row[second_cheapest_country] if row[cheapest_country] == 0.0 else min(row[cheapest_country],
                                                                                      row[second_cheapest_country])
            )

        country = cheapest_country if row[cheapest_country] == cheapest_price else second_cheapest_country

        # Append the result to the list
        result_list.append({'product_name': product_name, 'Country': country, 'Cheapest_Price': cheapest_price})

    # Create a DataFrame from the list of results
    result_df = pd.DataFrame(result_list)

    sum_basket = result_df['Cheapest_Price'].sum()
    print(f"Total cost of the basket in the cheapest country:{sum_basket:.2f}")

    print(result_df)
    export_to_csv(result_df, 'result_df_output.csv')

    return result_df, sum_basket


def export_to_csv(df, filename='product_prices.csv'):
    # Export DataFrame to a CSV file
    df.to_csv(filename, index=False)
    print(f'DataFrame exported to {filename}')


def extract_product_id_from_url(url):
    options = Options()
    options.headless = True
    options.add_argument('window-size=1920x1080')
    options.add_argument("--enable-logging")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    path = os.getenv('CHROMEDRIVER_PATH')

    driver = webdriver.Chrome(path, options=options)

    try:
        # Navigate to the URL
        driver.get(url)

        # Wait for the name element to be present on the page
        container_element = WebDriverWait(driver, 2).until(
            EC.visibility_of_element_located((By.CLASS_NAME, "productTilesWrapper_LkXSW"))
        )

        # Use BeautifulSoup to parse the HTML content of the container
        soup = BeautifulSoup(container_element.get_attribute("outerHTML"), 'html.parser')

        # Find all <li> elements within the container
        li_elements = soup.find_all('li')

        # Extract href values from each <li> element
        href_list = [li.find('a')['href'] for li in li_elements if li.find('a') and 'href' in li.find('a').attrs]
        product_id_list = [extract_asos_product_id(href) for href in href_list]

        return product_id_list

    finally:
        driver.quit()


def id_list_to_price_list(product_id_list):
    product_list = []

    for product_id in product_id_list:
        print(product_id)
        url = build_request_link(product_id)
        print(url)
        product_name, product_prices = extract_info_codembo_url(url)
        product_list.append((product_name, product_prices))

    return product_list
