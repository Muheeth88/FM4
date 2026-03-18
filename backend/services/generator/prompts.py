# Role-based prompt templates for Code Generator Agent

ROLE_PROMPTS = {
    "utility": """
Convert the following Java utility file into TypeScript.

Requirements:
- Use modern TypeScript
- Use ES modules (import/export)
- Do NOT use classes if not strictly required; prefer exported functions.
- Follow naming conventions: kebab-case for file names, camelCase for functions.
- Remove Java-specific constructs (e.g., static initializers, synchronized).
- Keep the business logic equivalent and robust.
""",
    "service": """
Convert the following Java API service/client file into a Playwright-compatible TypeScript service.

Requirements:
- Use async/await for all network calls.
- Use fetch or axios for HTTP requests.
- Return structured responses (e.g., interface/type defined for response body).
- Do NOT use static classes or Singletons; prefer exported functions or instances.
- Include proper error handling for network requests.
""",
    "page_object": """
Convert the following Selenium Page Object class into a Playwright Page Object in TypeScript.

Requirements:
- Use Playwright Locators (`page.locator()`) instead of `@FindBy` annotations.
- Use `async` functions for all actions (clicks, typing, navigation).
- Do NOT use Selenium-specific wait strategies; use Playwright's automatic waiting.
- Structure it as a class taking `Page` in the constructor.
- Use modern TypeScript structures.
""",
    "test": """
Convert the following Selenium/TestNG/JUnit test into a Playwright test script in TypeScript.

Requirements:
- Use `test('description', async ({ page }) => { ... })` format from `@playwright/test`.
- Use Playwright assertions (`await expect(...).toBeVisible()`).
- Chain Page Object calls correctly using `async/await`.
- Maintain test logic and assertions without translation to outdated patterns.
- Ensure the test run is entirely asynchronous.
"""
}

DEFAULT_PROMPT = """
Convert the following file into TypeScript for a Playwright-based framework.

Requirements:
- Use modern TypeScript and ES modules.
- Ensure type safety with proper interfaces or types.
- Follow best practices for asynchronous programming (async/await).
- Keep the original logic intact while adapting to the target framework standards.
"""
