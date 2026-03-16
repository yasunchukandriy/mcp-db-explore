BEGIN;

-- Customers
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL,
    country VARCHAR(2) NOT NULL DEFAULT 'DE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Categories
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT
);

-- Products
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    price NUMERIC(10, 2) NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_products_category_id ON products(category_id);

-- Orders
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'shipped', 'delivered', 'cancelled')),
    total NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(status);

-- Order items
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10, 2) NOT NULL
);

CREATE INDEX idx_order_items_order_id ON order_items(order_id);
CREATE INDEX idx_order_items_product_id ON order_items(product_id);

-- Seed data: customers (German names & cities)
INSERT INTO customers (email, first_name, last_name, city) VALUES
    ('hans.mueller@example.de', 'Hans', 'Mueller', 'Berlin'),
    ('anna.schmidt@example.de', 'Anna', 'Schmidt', 'München'),
    ('peter.weber@example.de', 'Peter', 'Weber', 'Hamburg'),
    ('maria.fischer@example.de', 'Maria', 'Fischer', 'Köln'),
    ('thomas.wagner@example.de', 'Thomas', 'Wagner', 'Frankfurt'),
    ('julia.becker@example.de', 'Julia', 'Becker', 'Stuttgart'),
    ('markus.hoffmann@example.de', 'Markus', 'Hoffmann', 'Düsseldorf'),
    ('sabine.schulz@example.de', 'Sabine', 'Schulz', 'Dresden'),
    ('stefan.koch@example.de', 'Stefan', 'Koch', 'Leipzig'),
    ('claudia.richter@example.de', 'Claudia', 'Richter', 'Nürnberg');

-- Seed data: categories
INSERT INTO categories (name, description) VALUES
    ('Elektronik', 'Smartphones, Laptops und Zubehör'),
    ('Kleidung', 'Herren- und Damenbekleidung'),
    ('Bücher', 'Romane, Sachbücher und Lehrmaterial'),
    ('Haushalt', 'Küchengeräte und Wohnaccessoires'),
    ('Sport', 'Sportausrüstung und Fitnesszubehör');

-- Seed data: products
INSERT INTO products (name, category_id, price, stock) VALUES
    ('iPhone 15 Pro', 1, 1199.00, 25),
    ('Samsung Galaxy S24', 1, 899.00, 30),
    ('MacBook Air M3', 1, 1299.00, 15),
    ('USB-C Ladekabel', 1, 12.99, 200),
    ('Winterjacke Herren', 2, 149.99, 40),
    ('Laufschuhe Damen', 2, 89.95, 55),
    ('Wollpullover', 2, 59.99, 70),
    ('Der Prozess - Kafka', 3, 9.99, 100),
    ('Python Crashkurs', 3, 29.99, 45),
    ('Sapiens - Harari', 3, 14.99, 60),
    ('Kaffeemaschine DeLuxe', 4, 249.00, 20),
    ('Staubsauger Turbo', 4, 199.00, 18),
    ('Mixer Pro 3000', 4, 79.00, 35),
    ('Yoga-Matte Premium', 5, 39.99, 80),
    ('Hanteln Set 20kg', 5, 69.99, 25);

-- Seed data: orders
INSERT INTO orders (customer_id, status, total, created_at) VALUES
    (1, 'delivered', 1211.99, '2025-01-15 10:30:00+01'),
    (2, 'delivered', 89.95, '2025-01-20 14:15:00+01'),
    (3, 'shipped', 1299.00, '2025-02-01 09:00:00+01'),
    (4, 'pending', 279.98, '2025-02-10 16:45:00+01'),
    (1, 'delivered', 29.99, '2025-02-14 11:20:00+01'),
    (5, 'cancelled', 149.99, '2025-02-20 08:30:00+01'),
    (6, 'shipped', 329.00, '2025-03-01 13:00:00+01'),
    (7, 'pending', 109.98, '2025-03-05 17:30:00+01'),
    (8, 'delivered', 249.00, '2025-03-10 10:00:00+01'),
    (3, 'shipped', 69.99, '2025-03-15 12:00:00+01'),
    (9, 'pending', 44.98, '2025-03-18 15:45:00+01'),
    (10, 'delivered', 899.00, '2025-03-20 09:30:00+01');

-- Seed data: order items
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
    (1, 1, 1, 1199.00),
    (1, 4, 1, 12.99),
    (2, 6, 1, 89.95),
    (3, 3, 1, 1299.00),
    (4, 11, 1, 249.00),
    (4, 9, 1, 29.99),
    (5, 9, 1, 29.99),
    (6, 5, 1, 149.99),
    (7, 11, 1, 249.00),
    (7, 13, 1, 79.00),
    (8, 14, 1, 39.99),
    (8, 15, 1, 69.99),
    (9, 11, 1, 249.00),
    (10, 15, 1, 69.99),
    (11, 8, 2, 9.99),
    (11, 10, 1, 14.99),
    (12, 2, 1, 899.00);

COMMIT;
