Your task is to fix the reported issues in the current branch.

You must strictly:
Follow Hexagonal Architecture (Ports & Adapters)
Follow the existing codebase patterns
Avoid architectural drift
Avoid duplication
Avoid mockups or placeholder implementations
Reuse existing components when possible
You are not allowed to introduce new patterns unless absolutely required and aligned with the codebase

🎯 Primary Objectives
Fix all reported issues correctly
Preserve architectural boundaries
Keep strict dependency direction
Maintain consistency with the existing project structure
Improve efficiency where possible
Avoid code duplication
Reuse existing services, utilities, mappers, helpers, or abstractions

🏗 Architectural Enforcement (STRICT)
You MUST ensure:

1️⃣ Dependency Direction
Adapters → Application → Domain
Domain must not depend on infrastructure
No framework logic in domain
No direct DB or HTTP usage in domain
Use ports for external communication
If a fix requires cross-layer access → refactor using proper ports

2️⃣ No Business Logic Leakage
No business logic in controllers
No business logic in repositories
No business logic in adapters
Business rules belong in Domain

3️⃣ Reusability Enforcement
Before adding new code:
Check if similar logic already exists
Reuse existing utilities
Reuse existing error handling strategy
Reuse existing logging pattern
Reuse existing mapper strategy
Reuse existing base classes if available
If reusable logic exists → use it
Do NOT duplicate code

4️⃣ No Mock Implementations
No TODO placeholders
No temporary stubs
No mock returns
No fake implementations
No simplified shortcuts
All fixes must be production-ready

5️⃣ Codebase Alignment
You MUST match:
Naming conventions
Folder structure
File organization
Logging style
Exception handling pattern
Dependency injection style
Repository pattern used in the project
DTO mapping approach used in the project
If unsure → follow the dominant pattern

🧹 Mandatory Refactor & Cleanup Enforcement (STRICT)
When modifying or refactoring logic, you MUST:

1️⃣ Replace — Not Layer
If logic changes → fully replace the old implementation
Do NOT stack new logic on top of old logic
Do NOT keep fallback paths unless explicitly required

2️⃣ Remove Obsolete Code
Delete previous implementations that are no longer used
Remove dead code branches
Remove unused methods
Remove unused classes
Remove unused interfaces
Remove unused imports
Remove obsolete DTOs / mappers if no longer needed

3️⃣ No Commented Leftovers
Do NOT comment out old logic
Do NOT keep legacy code blocks
Do NOT leave TODO markers for removed logic

4️⃣ Consistency Verification
After changes, verify:
No duplicate logic exists
No parallel implementations exist
No unused dependencies remain
The feature has a single clear execution path
Keeping obsolete or duplicated logic is considered a failure.

✨ Efficiency & Clean Code
While fixing:
Remove duplication
Remove dead code
Avoid unnecessary abstractions
Avoid over-engineering
Keep methods focused
Maintain SRP
Improve readability
Do NOT introduce architectural changes unless required to fix violations

📌 Required Output Format
You MUST respond with:

1️⃣ Summary of Fix Strategy
Explain how you approached the fix.

2️⃣ Detailed Changes
For each issue:
What was wrong
Why it violated architecture or codebase rules
What was changed
Why the new implementation is correct

3️⃣ Reuse Validation
List reusable components leveraged.

4️⃣ Duplication Check
Confirm whether duplication was removed or avoided.

5️⃣ Architecture Validation
Confirm:
Dependency direction respected
Layer separation maintained
No business logic leakage

6️⃣ Final Integrity Check
Confirm:
No mockups
No temporary fixes
Production-ready code

🚫 Forbidden Actions
Do NOT introduce new architectural styles
Do NOT move business logic outside the Domain
Do NOT duplicate code
Do NOT bypass ports
Do NOT simplify logic just to pass review
Do NOT change unrelated parts of the system

🎯 Mindset
You are fixing code for a:
Production system
Long-term maintainable architecture
Scalable application

Be strict.
Be precise.
Be aligned.
Be architectural.
