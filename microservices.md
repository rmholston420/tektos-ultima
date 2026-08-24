# Monolith-to-Microservices Decomposition Plan

## 1. Current Monolith Analysis

### 1.1 Module Inventory

| Module | Responsibility | Complexity | Business Criticality |
|--------|---------------|------------|---------------------|
| `auth` | User registration, login, RBAC | Low | High |
| `users` | Profiles, preferences, addresses | Medium | High |
| `catalog` | Product listing, categories, search | High | High |
| `orders` | Order creation, status, history | High | High |
| `payments` | Payment processing, refunds | Medium | High |
| `inventory` | Stock management, reservations | Medium | High |
| `notifications` | Email, SMS, push notifications | Low | Medium |
| `reports` | Analytics, dashboards | Medium | Low |
| `admin` | Admin panel, configuration | Low | Medium |

### 1.2 Dependency Map

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  auth    │────▶│  users   │────▶│ catalog  │
└──────────┘     └──────────┘     └──────────┘
                                         │
                                         ▼
┌──────────┐     ┌──────────┐     ┌──────────┐
│notifications│ │payments  │◀────│  orders  │
└──────────┘     └──────────┘     └──────────┘
                                         │
                                         ▼
                                   ┌──────────┐
                                   │inventory │
                                   └──────────┘
```

**Key dependency rules:**
- `orders` depends on `catalog` (product info), `inventory` (stock check), `payments` (processing)
- `payments` depends on `orders` (to link transactions)
- `notifications` depends on all modules (triggers on events)
- `auth` is foundational — no upstream dependencies
- `reports` reads from all modules (read-only)
- `admin` manages configuration for all modules

### 1.3 Data Flow Overview

- **Synchronous flows**: API calls within the monolith (in-process calls)
- **Asynchronous flows**: Internal event bus for notifications, reporting
- **Shared database**: Single PostgreSQL instance with all tables

---

## 2. Service Boundaries

Applying **Domain-Driven Design (DDD)** to define bounded contexts:

### 2.1 Bounded Contexts

| Service | Bounded Context | Aggregate Roots | Key Entities |
|---------|-----------------|-----------------|--------------|
| `identity-service` | Identity & Access | User, Role, Permission | user, role, session |
| `user-service` | Customer Profile | UserProfile, Address | profile, address, preference |
| `product-service` | Catalog | Product, Category, Review | product, category, review, price |
| `order-service` | Order Management | Order, OrderItem, Cart | order, item, cart |
| `payment-service` | Payments | Payment, Refund, Invoice | payment, refund, invoice |
| `inventory-service` | Stock Mgmt | StockItem, Reservation | stock, reservation |
| `notification-service` | Notifications | Notification, Template | notification, template, channel |
| `reporting-service` | Analytics | Report, Dashboard | report, dashboard, metric |

### 2.2 Context Mapping

```
[identity-service]────uses──▶[user-service]
       │                         │
       └─────────────────────────┘
         (shared identity concept)

[product-service]────uses──▶[order-service]
       │                         │
       │  knows about         knows about
       ▼                         ▼
[inventory-service]◀──reserves──[order-service]
       │
       └──publishes──▶[notification-service]

[payment-service]──depends on──[order-service]
       │
       └──publishes──▶[notification-service]

[reporting-service]──reads from── all services
```

**Boundary decisions:**
- **Split `auth` and `users`**: Auth is infrastructure concern; user profiles are business domain
- **Keep `orders` and `payments` separate**: Different change frequencies and team ownership
- **`inventory` is independent**: High concurrency writes, needs its own scaling
- **`notifications` as event consumer**: Pure subscriber, no direct client traffic
- **`reporting` as read-side service**: Denormalized copies, separate from transactional services

---

## 3. Migration Strategy

### 3.1 Strangler Fig Pattern — Phased Approach

```
Phase 1 (Weeks 1-4)    Phase 2 (Weeks 5-8)   Phase 3 (Weeks 9-12)  Phase 4 (Weeks 13-16)
┌─────────────┐       ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│  API Gateway │       │  API Gateway │       │  API Gateway │       │  API Gateway │
└──────┬──────┘       └──────┬──────┘       └──────┬──────┘       └──────┬──────┘
       │                     │                     │                     │
       ├──▶ identity-svc     ├──▶ user-svc         ├──▶ product-svc      ├──▶ order-svc
       │                     │                     │                     │
       └──▶ Monolith (rest)  ├──▶ Monolith         ├──▶ Monolith         ├──▶ payment-svc
       │                     │                     │                     │
       │                     └──▶ Monolith         ├──▶ Monolith         ├──▶ inventory-svc
       │                                          │                     │
       │                                          └──▶ Monolith         ├──▶ notification-svc
       │                                                       │        │
       │                                                       └──▶ Monolith └──▶ reporting-svc
       │                                                                    │
       └────────────────────────────────────────────────────────────────────┘
```

### 3.2 Phase Details

**Phase 1 — Foundation (identity-service)**
- Extract authentication; set up API gateway
- Route `/auth/**` to new service; rest to monolith
- Implement OAuth2/JWT token service
- Database: separate `users` schema

**Phase 2 — Core entities (user-service, product-service)**
- Extract user profiles and product catalog
- Implement request routing at gateway level
- Database: separate schemas for each
- Begin event publishing for user/product changes

**Phase 3 — Transactional domain (order-service, payment-service)**
- Extract order and payment flows
- Implement saga pattern for order creation
- Database: separate per service
- Bidirectional coordination via events

**Phase 4 — Supporting services (inventory, notifications, reporting)**
- Extract remaining services
- Decommission monolith routes
- Final cutover and cleanup

### 3.3 Rollback Strategy

- Each phase maintains dual-write capability for 2 weeks
- Feature flags control routing (gateway-level)
- Database migrations are additive-only until cutover
- If issues detected: disable feature flag, route to monolith, revert service deployment

---

## 4. Inter-Service Communication

### 4.1 API Gateway

- **Technology**: Kong / AWS API Gateway / Spring Cloud Gateway
- **Responsibilities**:
  - Request routing to appropriate service
  - Authentication / JWT validation
  - Rate limiting and circuit breaking
  - Request/response transformation
  - SSL termination

```yaml
# Example gateway routing
routes:
  - path: /auth/**        → identity-service:8081
  - path: /users/**       → user-service:8082
  - path: /products/**    → product-service:8083
  - path: /orders/**      → order-service:8084
  - path: /payments/**    → payment-service:8085
  - path: /inventory/**   → inventory-service:8086
  - path: /notifications/** → notification-service:8087
  - path: /reports/**     → reporting-service:8088
```

### 4.2 Synchronous Communication (REST/gRPC)

**Use when:**
- Immediate response is required
- Request-response pattern fits naturally

**Rules:**
- Services communicate via REST (JSON) or gRPC for performance-critical paths
- No direct DB access between services
- All cross-service calls go through API gateway
- Implement retry with exponential backoff and circuit breaker (e.g., Resilience4j)

### 4.3 Asynchronous Communication (Event-Driven)

**Technology**: Apache Kafka or RabbitMQ

**Event Catalog:**

| Event | Source | Consumers | Schema Version |
|-------|--------|-----------|----------------|
| `UserRegistered` | identity-service | user-service, notification-service | v1 |
| `UserUpdated` | user-service | notification-service, reporting-service | v1 |
| `ProductCreated` | product-service | notification-service | v1 |
| `ProductPriceChanged` | product-service | order-service (cached prices) | v1 |
| `OrderCreated` | order-service | payment-svc, inventory-svc, notification-svc | v1 |
| `OrderStatusChanged` | order-service | notification-service, reporting-service | v1 |
| `PaymentCompleted` | payment-service | order-service, notification-service | v1 |
| `PaymentFailed` | payment-service | order-service, notification-service | v1 |
| `StockReserved` | inventory-service | order-service | v1 |
| `StockReleased` | inventory-service | order-service | v1 |

**Event patterns:**
- **Publish-Subscribe**: One event → multiple consumers (e.g., `OrderCreated`)
- **Request-Reply**: Via correlation IDs for synchronous needs over async
- **Dead Letter Queue**: For failed event processing (manual retry or alert)

### 4.4 Service Discovery & Configuration

- **Discovery**: HashiCorp Consul or Kubernetes native service discovery
- **Configuration**: Centralized config server (e.g., Spring Cloud Config / Consul Config)
- **Health checks**: Liveness and readiness probes (Kubernetes-style)

---

## 5. Data Migration

### 5.1 Database Per Service Strategy

| Service | Database | Schema | Notes |
|---------|----------|--------|-------|
| identity-service | PostgreSQL | `identity` | Isolated from day one |
| user-service | PostgreSQL | `users` | Shared columns migrated from monolith |
| product-service | PostgreSQL | `products` | Includes price, inventory refs |
| order-service | PostgreSQL | `orders` | Denormalize product snapshot at order time |
| payment-service | PostgreSQL | `payments` | Separate from order data |
| inventory-service | PostgreSQL | `inventory` | Optimistic locking for stock updates |
| notification-service | PostgreSQL | `notifications` | Append-only, no foreign keys |
| reporting-service | PostgreSQL | `reporting` | Denormalized read-optimized schema |

### 5.2 Migration Steps

1. **Dual-write (Weeks 1-4)**
   - Monolith writes to both old table and new service schema
   - Background sync script fills gap for historical data
   - Read from monolith; verify write consistency

2. **Read split (Weeks 5-8)**
   - Route reads to new service for extracted modules
   - Keep dual-write active
   - Monitor data consistency between old and new

3. **Cutover (Weeks 9-12)**
   - Stop dual-write
   - Verify data integrity
   - Drop old monolith tables for migrated modules

4. **Decommission (Weeks 13-16)**
   - Remove monolith code for migrated features
   - Archive old tables (retain for 90 days)
   - Final cleanup

### 5.3 Eventual Consistency — Saga Pattern

```
Order Creation Saga (Orchestrator approach):

order-service:
  1. Create Order (status: PENDING)
  2. Publish OrderCreated event

inventory-service:
  3. Receive OrderCreated event
  4. Reserve stock
  5. Publish StockReserved event
  6. OR publish StockReservationFailed event

payment-service:
  7. Receive StockReserved event
  8. Process payment
  9. Publish PaymentCompleted event
  10. OR publish PaymentFailed event

order-service (continues):
  11. Receive PaymentCompleted → Order (status: CONFIRMED)
  11b. Receive PaymentFailed → Order (status: PAYMENT_FAILED)
  11c. Receive StockReservationFailed → Order (status: PROCESSING_FAILED)
```

**Compensating Actions (Rollbacks):**
- Payment failed → release inventory reservation
- Stock unavailable → cancel order
- Order cancelled → refund payment

**Consistency guarantees:**
- **Reads**: May be stale for up to 5 seconds (accept eventual consistency)
- **Writes**: Strong consistency within a single service
- **Cross-service**: Eventual consistency via saga orchestration
- **Critical paths**: Use distributed transactions (2PC) only for payment confirmation

### 5.4 Data Consistency Verification

```
Post-migration checks:
  □ Row counts match between old and new schemas
  □ Sample records: old DB ↔ new service API
  □ Event replay: replay 24h of events, verify final state
  □ Financial reconciliation: payment totals match
  □ Performance: query latency < 200ms p95
```

---

## 6. Implementation Checklist

### Prerequisites
- [ ] Container orchestration (Kubernetes or Docker Compose)
- [ ] CI/CD pipeline per service
- [ ] Monitoring stack (Prometheus + Grafana)
- [ ] Distributed tracing (Jaeger or Zipkin)
- [ ] Log aggregation (ELK or Loki)

### Per Phase
- [ ] Service code written and tested
- [ ] Database schema created and migrated
- [ ] API contract defined (OpenAPI spec)
- [ ] Event schemas versioned
- [ ] Integration tests with dependent services
- [ ] Load testing at 2x expected traffic
- [ ] Feature flag enabled, monitoring active
- [ ] Rollback procedure tested

### Post-Migration
- [ ] Monolith decommissioned
- [ ] Shared database tables dropped
- [ ] Team runbooks created for each service
- [ ] On-call rotation established
- [ ] Cost analysis reviewed

---

## 7. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data inconsistency during split | High | Dual-write + verification scripts |
| Increased latency from network calls | Medium | gRPC for hot paths; caching |
| Distributed debugging complexity | Medium | Distributed tracing from day one |
| Team coordination overhead | Medium | Clear service ownership; API contracts |
| Event ordering issues | Low | Kafka partitioning by entity ID |
| Cascading failures | High | Circuit breakers + bulkheads |

---

*Plan prepared for a typical e-commerce monolith. Adjust service boundaries and timelines based on actual complexity and team size.*
