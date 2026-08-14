"""Architecture Template Selector.

Presents user with predefined architecture templates and selects the best fit.
Not ad-hoc decisions — standardized formats the Planner can select from.

Templates:
- Vertical Slice: Feature-oriented, each slice contains UI→logic→data
- Horizontal Layered: Layer-oriented (UI layer, service layer, data layer)
- Kernel + Extensions: Core system + pluggable modules
- Microservices: Independent deployable services
"""

from __future__ import annotations

from .models import ArchitectureChoice, ArchitectureTemplate

# Predefined architecture templates
TEMPLATES: list[ArchitectureTemplate] = [
    ArchitectureTemplate(
        name="vertical_slice",
        description="Feature-oriented architecture. Each slice contains UI→logic→data end-to-end. "
        "Slices are independent and can be developed/tested/deployed separately.",
        pros=[
            "Clear feature boundaries — each slice is a complete feature",
            "Independent development — slices can work in parallel",
            "Easy to understand — each slice is a self-contained unit",
            "Easy to test — each slice has its own test surface",
            "Easy to deploy — slices can be deployed independently",
        ],
        cons=[
            "Code duplication across slices (shared logic extracted to kernel)",
            "Cross-cutting concerns (auth, logging) must be repeated in each slice",
            "Can lead to inconsistent patterns across slices",
            "Best for small-to-medium teams (2-8 developers)",
        ],
        use_cases=[
            "Small to medium applications",
            "Feature-rich applications with many independent features",
            "Teams that want to move fast with clear ownership",
            "Applications with evolving feature sets",
        ],
        recommended_for="Small-to-medium teams building feature-rich applications with clear boundaries",
    ),
    ArchitectureTemplate(
        name="horizontal_layered",
        description="Layer-oriented architecture. Distinct layers (presentation, application, domain, infrastructure) "
        "with strict unidirectional dependencies. Each layer serves the one above it.",
        pros=[
            "Clear separation of concerns — each layer has a single responsibility",
            "Easy to reason about — data flows in one direction",
            "Easy to test — each layer can be tested in isolation",
            "Well-understood pattern — most developers know layered architecture",
            "Easy to swap layers — replace one layer without affecting others",
        ],
        cons=[
            "Can lead to 'fat layers' where one layer has too many responsibilities",
            "Cross-cutting concerns still need handling (AOP, middleware)",
            "Can be rigid — adding new features may require changes across all layers",
            "Best for large teams with clear role separation",
        ],
        use_cases=[
            "Large enterprise applications",
            "Applications with strict compliance requirements",
            "Teams with clear role separation (frontend, backend, database)",
            "Applications with long lifespans requiring maintenance",
        ],
        recommended_for="Large teams building enterprise applications with strict compliance and clear role separation",
    ),
    ArchitectureTemplate(
        name="kernel_extensions",
        description="Core kernel with pluggable extensions. The kernel handles common functionality "
        "(routing, auth, logging, configuration). Extensions plug into the kernel via well-defined interfaces.",
        pros=[
            "Kernel is stable and well-tested — extensions add new capabilities",
            "Extensions are independent — can be developed/tested/replaced separately",
            "Easy to onboard — new extensions follow kernel patterns",
            "Easy to maintain — kernel changes rarely affect extensions",
            "Strong foundation — kernel provides shared infrastructure",
        ],
        cons=[
            "Kernel must anticipate future extension points (forward-looking design)",
            "Extensions must conform to kernel interfaces (some rigidity)",
            "Kernel bloat risk — kernel can grow too large over time",
            "Requires careful interface design — bad interfaces constrain extensions",
        ],
        use_cases=[
            "Applications with many similar features (e.g., a platform)",
            "Applications where plugins/extensions are a core requirement",
            "Applications with multiple similar variants (SaaS white-labeling)",
            "Applications that need to support third-party extensions",
        ],
        recommended_for="Applications that need pluggable extensions or multiple similar variants",
    ),
    ArchitectureTemplate(
        name="microservices",
        description="Independent deployable services. Each service owns its data, logic, and deployment. "
        "Services communicate via well-defined APIs (HTTP, gRPC, messaging).",
        pros=[
            "Independent deployment — services can be deployed without affecting others",
            "Independent scaling — services can scale based on their own load",
            "Technology diversity — each service can use the best technology",
            "Fault isolation — service failures don't bring down the whole system",
            "Team autonomy — each team owns their service end-to-end",
        ],
        cons=[
            "High operational overhead — monitoring, logging, tracing required",
            "Network complexity — service calls are unreliable and slow",
            "Data consistency challenges — distributed transactions are hard",
            "Testing complexity — testing across services requires integration tests",
            "Best for large teams (8+ developers) with DevOps expertise",
        ],
        use_cases=[
            "Large-scale applications (100k+ users)",
            "Applications with highly variable load patterns",
            "Applications with multiple independent business domains",
            "Organizations with multiple autonomous teams",
        ],
        recommended_for="Large-scale applications with multiple autonomous teams and DevOps expertise",
    ),
]


def select_best_templates(
    requirements: list[str],
    count: int = 3,
) -> list[ArchitectureTemplate]:
    """Select the best-fit architecture templates for the given requirements.

    Scores each template against the requirements using keyword matching.
    Returns the top N templates sorted by score.

    Args:
        requirements: List of requirement strings from the user prompt.
        count: Number of templates to return (default: 3).

    Returns:
        List of ArchitectureTemplates sorted by fit score (highest first).
    """
    scored = [(tpl, tpl.score(requirements)) for tpl in TEMPLATES]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [tpl for tpl, _ in scored[:count]]


def choose_best_template(
    requirements: list[str],
    user_preference: str | None = None,
) -> ArchitectureChoice:
    """Choose the best-fit architecture template.

    If user_preference is provided, uses it. Otherwise, selects the highest-scoring
    template based on requirements analysis.

    Args:
        requirements: List of requirement strings from the user prompt.
        user_preference: Optional user-preferred template name.

    Returns:
        ArchitectureChoice with the selected template and reason.
    """
    if user_preference:
        for tpl in TEMPLATES:
            if tpl.name == user_preference:
                return ArchitectureChoice(
                    selected=tpl.name,
                    reason=f"User selected {tpl.name} over other options",
                    is_user_choice=True,
                )
        # User preference not found — fall back to scoring
        # (log a warning in production)

    # Score and select best fit
    scored = [(tpl, tpl.score(requirements)) for tpl in TEMPLATES]
    scored.sort(key=lambda x: x[1], reverse=True)
    best = scored[0]

    return ArchitectureChoice(
        selected=best[0].name,
        reason=f"Best fit for requirements: {best[0].recommended_for}",
        is_user_choice=False,
    )
