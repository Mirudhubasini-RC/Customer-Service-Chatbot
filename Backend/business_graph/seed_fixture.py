"""
Offline fixture matching Backend/seed.sql DEMO/ENRICHED + preserved products/sales.
Used by demo/tests when MySQL is unavailable.
"""

SEED_BRANDS = [
    {'brand_id': 1, 'brand_name': 'TechNova'},
    {'brand_id': 2, 'brand_name': 'SoundMax'},
    {'brand_id': 3, 'brand_name': 'DeskPro'},
    {'brand_id': 4, 'brand_name': 'PowerLink'},
    {'brand_id': 5, 'brand_name': 'ViewClear'},
]

SEED_CATEGORIES = [
    {'category_id': 1, 'category_name': 'Computers'},
    {'category_id': 2, 'category_name': 'Mobile'},
    {'category_id': 3, 'category_name': 'Audio'},
    {'category_id': 4, 'category_name': 'Accessories'},
    {'category_id': 5, 'category_name': 'Furniture'},
    {'category_id': 6, 'category_name': 'Networking'},
]

SEED_ISSUES = [
    {'issue_id': 1, 'issue_name': 'Defective product'},
    {'issue_id': 2, 'issue_name': 'Late delivery'},
    {'issue_id': 3, 'issue_name': 'Wrong item received'},
    {'issue_id': 4, 'issue_name': 'Pricing concern'},
    {'issue_id': 5, 'issue_name': 'Battery life'},
    {'issue_id': 6, 'issue_name': 'Durability'},
    {'issue_id': 7, 'issue_name': 'Compatibility'},
    {'issue_id': 8, 'issue_name': 'Packaging damage'},
]

SEED_PRODUCTS = [
    {'product_id': 1, 'product_name': 'Laptop', 'price': 999.99, 'brand_id': 1, 'category_id': 1},
    {'product_id': 2, 'product_name': 'Smartphone', 'price': 799.99, 'brand_id': 1, 'category_id': 2},
    {'product_id': 3, 'product_name': 'Headphones', 'price': 149.99, 'brand_id': 2, 'category_id': 3},
    {'product_id': 4, 'product_name': 'Monitor', 'price': 199.99, 'brand_id': 5, 'category_id': 1},
    {'product_id': 5, 'product_name': 'Keyboard', 'price': 49.99, 'brand_id': 4, 'category_id': 4},
    {'product_id': 6, 'product_name': 'Mouse', 'price': 29.99, 'brand_id': 4, 'category_id': 4},
    {'product_id': 7, 'product_name': 'Smartwatch', 'price': 199.99, 'brand_id': 1, 'category_id': 2},
    {'product_id': 8, 'product_name': 'Tablet', 'price': 499.99, 'brand_id': 1, 'category_id': 2},
    {'product_id': 9, 'product_name': 'Printer', 'price': 89.99, 'brand_id': 4, 'category_id': 4},
    {'product_id': 10, 'product_name': 'Webcam', 'price': 59.99, 'brand_id': 5, 'category_id': 4},
    {'product_id': 11, 'product_name': 'External Hard Drive', 'price': 129.99, 'brand_id': 4, 'category_id': 4},
    {'product_id': 12, 'product_name': 'Router', 'price': 69.99, 'brand_id': 4, 'category_id': 6},
    {'product_id': 13, 'product_name': 'Speaker', 'price': 89.99, 'brand_id': 2, 'category_id': 3},
    {'product_id': 14, 'product_name': 'Desk Chair', 'price': 179.99, 'brand_id': 3, 'category_id': 5},
    {'product_id': 15, 'product_name': 'Standing Desk', 'price': 299.99, 'brand_id': 3, 'category_id': 5},
    {'product_id': 16, 'product_name': 'Desk Lamp', 'price': 39.99, 'brand_id': 3, 'category_id': 5},
    {'product_id': 17, 'product_name': 'USB Hub', 'price': 19.99, 'brand_id': 4, 'category_id': 4},
    {'product_id': 18, 'product_name': 'Charger', 'price': 24.99, 'brand_id': 4, 'category_id': 4},
    {'product_id': 19, 'product_name': 'Power Bank', 'price': 34.99, 'brand_id': 4, 'category_id': 4},
    {'product_id': 20, 'product_name': 'Memory Card', 'price': 15.99, 'brand_id': 4, 'category_id': 4},
    {'product_id': 21, 'product_name': 'Gaming Chair', 'price': 249.99, 'brand_id': 3, 'category_id': 5},
    {'product_id': 22, 'product_name': 'USB-C Hub', 'price': 39.99, 'brand_id': 4, 'category_id': 4},
    {'product_id': 23, 'product_name': 'Gaming Chair', 'price': 249.99, 'brand_id': 3, 'category_id': 5},
    {'product_id': 24, 'product_name': 'USB-C Hub', 'price': 39.99, 'brand_id': 4, 'category_id': 4},
]

SEED_SALES = [
    {'sale_id': 1, 'product_id': 1, 'sale_date': '2024-08-01', 'quantity': 10, 'total_price': 9999.90},
    {'sale_id': 2, 'product_id': 2, 'sale_date': '2024-08-02', 'quantity': 15, 'total_price': 11999.85},
    {'sale_id': 3, 'product_id': 3, 'sale_date': '2024-08-03', 'quantity': 25, 'total_price': 3749.75},
    {'sale_id': 4, 'product_id': 4, 'sale_date': '2024-08-04', 'quantity': 12, 'total_price': 2399.88},
    {'sale_id': 5, 'product_id': 5, 'sale_date': '2024-08-05', 'quantity': 20, 'total_price': 999.80},
    {'sale_id': 6, 'product_id': 6, 'sale_date': '2024-08-06', 'quantity': 30, 'total_price': 899.70},
    {'sale_id': 7, 'product_id': 7, 'sale_date': '2024-08-07', 'quantity': 18, 'total_price': 3599.82},
    {'sale_id': 8, 'product_id': 8, 'sale_date': '2024-08-08', 'quantity': 22, 'total_price': 10999.78},
    {'sale_id': 9, 'product_id': 9, 'sale_date': '2024-08-09', 'quantity': 5, 'total_price': 449.95},
    {'sale_id': 10, 'product_id': 10, 'sale_date': '2024-08-10', 'quantity': 14, 'total_price': 839.86},
    {'sale_id': 11, 'product_id': 11, 'sale_date': '2024-08-11', 'quantity': 8, 'total_price': 1039.92},
    {'sale_id': 12, 'product_id': 12, 'sale_date': '2024-08-12', 'quantity': 25, 'total_price': 1749.75},
    {'sale_id': 13, 'product_id': 13, 'sale_date': '2024-08-13', 'quantity': 9, 'total_price': 629.91},
    {'sale_id': 14, 'product_id': 14, 'sale_date': '2024-08-14', 'quantity': 6, 'total_price': 539.94},
    {'sale_id': 15, 'product_id': 15, 'sale_date': '2024-08-15', 'quantity': 11, 'total_price': 1979.89},
    {'sale_id': 16, 'product_id': 16, 'sale_date': '2024-08-16', 'quantity': 17, 'total_price': 1799.83},
    {'sale_id': 17, 'product_id': 17, 'sale_date': '2024-08-17', 'quantity': 8, 'total_price': 319.92},
    {'sale_id': 18, 'product_id': 18, 'sale_date': '2024-08-18', 'quantity': 12, 'total_price': 419.88},
    {'sale_id': 19, 'product_id': 19, 'sale_date': '2024-08-19', 'quantity': 14, 'total_price': 489.86},
    {'sale_id': 20, 'product_id': 20, 'sale_date': '2024-08-20', 'quantity': 5, 'total_price': 79.95},
    {'sale_id': 21, 'product_id': 1, 'sale_date': '2026-08-01', 'quantity': 4, 'total_price': 3999.96},
    {'sale_id': 22, 'product_id': 6, 'sale_date': '2026-08-02', 'quantity': 20, 'total_price': 599.80},
    {'sale_id': 23, 'product_id': 1, 'sale_date': '2026-08-01', 'quantity': 4, 'total_price': 3999.96},
    {'sale_id': 24, 'product_id': 6, 'sale_date': '2026-08-02', 'quantity': 20, 'total_price': 599.80},
]

SEED_FEEDBACK = [
    {
        'feedback_id': 1, 'product_id': 1, 'issue_id': 1,
        'feedback_text': 'Laptop screen developed dead pixels within two weeks of purchase.',
        'sentiment': 'negative', 'is_return': 1, 'return_reason': 'Defective display',
        'feedback_date': '2024-08-20 10:15:00',
    },
    {
        'feedback_id': 2, 'product_id': 1, 'issue_id': 5,
        'feedback_text': 'Battery lasts barely 3 hours under light office use.',
        'sentiment': 'negative', 'is_return': 0, 'return_reason': None,
        'feedback_date': '2024-08-22 14:30:00',
    },
    {
        'feedback_id': 3, 'product_id': 2, 'issue_id': None,
        'feedback_text': 'Smartphone camera quality is excellent for the price.',
        'sentiment': 'positive', 'is_return': 0, 'return_reason': None,
        'feedback_date': '2024-08-18 09:05:00',
    },
    {
        'feedback_id': 4, 'product_id': 3, 'issue_id': 6,
        'feedback_text': 'Headphones ear cushions tore after one month of daily use.',
        'sentiment': 'negative', 'is_return': 1, 'return_reason': 'Poor durability',
        'feedback_date': '2024-08-25 16:40:00',
    },
    {
        'feedback_id': 5, 'product_id': 3, 'issue_id': None,
        'feedback_text': 'Sound clarity is great for calls and music.',
        'sentiment': 'positive', 'is_return': 0, 'return_reason': None,
        'feedback_date': '2024-08-12 11:20:00',
    },
    {
        'feedback_id': 6, 'product_id': 6, 'issue_id': 7,
        'feedback_text': 'Mouse pairing drops frequently with older laptops.',
        'sentiment': 'negative', 'is_return': 0, 'return_reason': None,
        'feedback_date': '2024-08-19 13:10:00',
    },
    {
        'feedback_id': 7, 'product_id': 7, 'issue_id': 5,
        'feedback_text': 'Smartwatch battery drains overnight even with low usage.',
        'sentiment': 'negative', 'is_return': 1, 'return_reason': 'Battery failure',
        'feedback_date': '2024-08-28 08:45:00',
    },
    {
        'feedback_id': 8, 'product_id': 8, 'issue_id': 2,
        'feedback_text': 'Tablet arrived 8 days later than the promised delivery window.',
        'sentiment': 'negative', 'is_return': 0, 'return_reason': None,
        'feedback_date': '2024-08-21 17:55:00',
    },
    {
        'feedback_id': 9, 'product_id': 12, 'issue_id': None,
        'feedback_text': 'Router setup was simple and coverage is strong across rooms.',
        'sentiment': 'positive', 'is_return': 0, 'return_reason': None,
        'feedback_date': '2024-08-15 12:00:00',
    },
    {
        'feedback_id': 10, 'product_id': 12, 'issue_id': 7,
        'feedback_text': 'Router firmware update broke compatibility with some IoT devices.',
        'sentiment': 'negative', 'is_return': 0, 'return_reason': None,
        'feedback_date': '2024-09-01 19:25:00',
    },
    {
        'feedback_id': 11, 'product_id': 14, 'issue_id': 8,
        'feedback_text': 'Desk chair box arrived crushed; foam was compressed.',
        'sentiment': 'negative', 'is_return': 1, 'return_reason': 'Packaging damage',
        'feedback_date': '2024-08-23 15:05:00',
    },
    {
        'feedback_id': 12, 'product_id': 15, 'issue_id': None,
        'feedback_text': 'Standing desk is sturdy and height adjustment is smooth.',
        'sentiment': 'positive', 'is_return': 0, 'return_reason': None,
        'feedback_date': '2024-08-27 10:50:00',
    },
    {
        'feedback_id': 13, 'product_id': 4, 'issue_id': 4,
        'feedback_text': 'Monitor price jumped right after my purchase; felt overcharged.',
        'sentiment': 'neutral', 'is_return': 0, 'return_reason': None,
        'feedback_date': '2024-08-16 18:30:00',
    },
    {
        'feedback_id': 14, 'product_id': 19, 'issue_id': 3,
        'feedback_text': 'Ordered a power bank but received a charger instead.',
        'sentiment': 'negative', 'is_return': 1, 'return_reason': 'Wrong item received',
        'feedback_date': '2024-08-29 09:40:00',
    },
    {
        'feedback_id': 15, 'product_id': 10, 'issue_id': None,
        'feedback_text': 'Webcam image is clear for remote meetings.',
        'sentiment': 'positive', 'is_return': 0, 'return_reason': None,
        'feedback_date': '2024-08-14 20:10:00',
    },
]


def seed_records():
    return {
        'brands': SEED_BRANDS,
        'categories': SEED_CATEGORIES,
        'issues': SEED_ISSUES,
        'products': SEED_PRODUCTS,
        'sales': SEED_SALES,
        'customer_feedback': SEED_FEEDBACK,
    }
