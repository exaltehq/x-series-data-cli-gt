JIRA: Spike + Plan
Title: CLI tool to generate demo customers and products in X-Series using personal access token

Type: Spike (investigation + planning)

Background
Partners frequently request “quality demo data” in their X-Series accounts (realistic customer identities and products) to validate integrations and demos. We want a lightweight CLI that can create a baseline dataset quickly using the X-Series API.

Goal
Design and spec a CLI tool that:

* Accepts a domain prefix and personal access token
* Prompts the user to select product “types” (vertical packs) backed by Faker e-commerce style data
* Creates 50 products and 50 customers by default using X-Series endpoints
* Leaves sales generation to the existing random sales creation tool (handled separately)

Proposed CLI UX flow (interactive)

1. Prompt: Enter domain prefix
2. Prompt: Enter personal access token (masked input, also allow env var)
3. Prompt: Select dataset pack(s)

   * Example: Apparel, Grocery/CPG, Electronics, Beauty, Home Goods, Services (non-inventory)
4. Prompt: Confirm counts

   * Default: 50 products, 50 customers
   * Optional overrides: --products N, --customers N
5. Execution progress output

   * Create customers first, then products
   * Show progress and summary
6. Output artifacts

   * Print counts created
   * Write JSON mapping file: customers (email -> customer_id), products (sku -> product_id)

Scope for this ticket (investigation + plan)

* Identify the exact X-Series endpoints for:

  * Customer creation
  * Product creation
* Pull and review the OpenAPI JSON to confirm:

  * Required fields for customer create and product create
  * Field constraints and formats (SKU uniqueness, email uniqueness rules, max lengths, required nested objects)
  * Price format and whether it is inclusive/exclusive of tax
  * Whether supplier/vendor mapping is supported directly at create time, and how categories/tags are represented
  * Whether images are supported at create time, and if URLs are accepted (or skip images)
* Document rate limits and recommended request pacing and retry behavior
* Produce a minimal functional spec for implementation (inputs, flow, outputs, guardrails)

Non-goals (explicitly out of scope)

* OAuth2 flow support (use personal access tokens only for v1)
* Sales generation within this tool (use existing random sales creation tool)
* Multi-tenant orchestration or UI beyond the CLI

Deliverables

* Short spec document in the ticket (or linked doc) containing:

  * Endpoints and payload shapes for customer and product creation
  * Required vs optional fields list
  * Proposed vertical “packs” and the field population rules per pack
  * Decisions or recommendations for:

    * Dummy email domain strategy (example.com style)
    * Price format and defaults
    * Supplier/category/tag handling
    * Image handling (skip vs placeholder URLs)
  * Proposed CLI interface:

    * interactive prompts
    * flags (non-interactive mode)
    * output files

Acceptance criteria

* OpenAPI JSON retrieved and reviewed, with citations in the ticket notes: endpoints, request/response schemas, and required fields for customer/product creation
* Confirmed implementation feasibility for:

  * Creating 50 customers and 50 products with minimal required fields
  * Faker-based generation producing valid payloads
* Documented constraints and defaults for:

  * Email and SKU uniqueness approach
  * Price and tax handling approach
  * Whether supplier/categories/images can be included or must be skipped initially
* Proposed CLI UX (prompt sequence) and command flags defined
* Clear “next implementation ticket” breakdown created (customers module, products module, datasets/packs, output/mapping, retries/throttling)

Notes / Open decisions to finalize during the spike

* Dummy email domain: use reserved domains (example.com / example.org) and unique local parts
* Price: confirm inclusive vs exclusive rules from OpenAPI and set a consistent default
* Supplier/category/tag/images: confirm what is supported in create calls; otherwise defer to v2 enhancements
