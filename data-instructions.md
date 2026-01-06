Recommendation: use Python Faker for customers, plus faker-commerce for products

Why this combo

* Faker is the most widely used Python fake-data library and covers customer fields cleanly (name, email, phone, address). ([GitHub][1])
* faker-commerce plugs into Faker and gives you productName, price, category/department, and description-style fields out of the box. ([PyPI][2])
* You can keep everything in one generator and add your own “vertical packs” as simple lists without needing separate datasets.

Four tangible vertical packs (non-food)

1. Apparel
2. Electronics
3. Home & Kitchen
4. Health & Beauty

How to implement verticals using this stack (simple and effective)

* Use faker-commerce to generate the base product name and description. ([PyPI][2])
* Override categories/tags with your own curated lists per vertical (small JSON arrays in the repo).
* Constrain price ranges per vertical (ex: Apparel 15–120, Electronics 50–1200, Home 10–300, Beauty 8–120).
* SKU: generate deterministic SKUs from (vertical prefix + random digits) and enforce uniqueness in-memory before POSTing.

Dummy emails

* Use Faker to generate local parts, but force the domain to a reserved domain like example.com to avoid any chance of emailing real addresses.

If you prefer Node instead

* @faker-js/faker is strong and includes a commerce module (productName, productDescription, department, price). ([Faker.js][3])
* Only choose this if the CLI will be built in Node/TS anyway.

If you want maximum control/performance later

* Mimesis is a good upgrade path, but for speed of delivery and maintainability, Faker + faker-commerce is the most straightforward starting point. ([mimesis.name][4])

[1]: https://github.com/joke2k/faker?utm_source=chatgpt.com "Faker is a Python package that generates fake data for you."
[2]: https://pypi.org/project/faker-commerce/?utm_source=chatgpt.com "faker-commerce"
[3]: https://fakerjs.dev/api/commerce?utm_source=chatgpt.com "Commerce | Faker"
[4]: https://mimesis.name/?utm_source=chatgpt.com "Mimesis: Fake Data Generator — Mimesis 19.0.0 documentation"
