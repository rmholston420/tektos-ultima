# Monolith-to-Microservices Decomposition Plan

## 1. Current Monolith Analysis

### 1.1 Modules

| Module | Responsibility | Complexity | Change Frequency |
|--------|---------------|------------|------------------|
| **User Service** | Authentication, profiles, permissions | Medium | High |
| **Order Service** | Order creation, status tracking | High | High |
| **Inventory Service** | Stock management, reservations | Medium | Medium |
| **Payment Service** | Payment processing, refunds | High | Low |
| **Notification Service** | Email, SMS, push notifications | Low | Medium |
| **Reporting Service** | Analytics, dashboards | Medium | Low |
| **Search Service** | Product catalog search | Medium | Medium |

### 1.2 Dependencies

```
                  ┌─────────────┐
                  │  Frontend   │
                  └──────┬──────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
   ┌──────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐
   │  User Mgmt  │ │  Orders  │ │ Inventory   │
   └──────┬──────┘ └────┬─────┘ └──────┬──────┘
          │              │              │
   ┌──────▼──────────────▼──────────────▼──────┐
   │           Monolithic Codebase             │
   │   (Shared DB, Shared Business Logic)      │
   └───────────────────────────────────────────┘
```

**Key dependency issues:**
- Tight coupling between Order and Inventory (synchronous calls within same process)
- Shared database prevents independent deployment
- Cross-module imports create compile-time dependencies
- Circular dependencies between Payment and Order modules

### 1.3 Data Flows

```
User → Order → Payment → Inventory → Notification
                    ↑          ↓
              (refund)  (update)
                    
Reporting reads from all modules (direct DB queries)
Search indexes from Product + Order data
```

---

## 2. Service Boundaries (Domain-Driven Design)

### 2.1 Bounded Contexts

| Context | Bounded Context | Aggregate Roots | Key Invariants |
|---------|----------------|-----------------|----------------|
| **Identity** | User Bounded Context | User, Role, Permission | Each user has one active session |
| **Commerce** | Order Bounded Context | Order, OrderItem | Order total = sum of items + tax |
| **Warehouse** | Inventory Bounded Context | Product, StockReservation | Reserved + available = total |
| **Finance** | Payment Bounded Context | Payment, Refund | Payment status is monotonic |
| **Communication** | Notification Bounded Context | Notification, Template | Notification is idempotent |
| **Discovery** | Catalog Bounded Context | Product, Category | Product has one primary category |

### 2.2 Context Map

```
┌──────────────┐    domain events    ┌──────────────┐
│   Identity   │────────────────────▶│   Commerce   │
│              │                     │              │
└──────────────┘                     │  ┌──────────┐│
                                     │  │Payment   ││
                                     │  └────┬────┘│
                                     │       │      │
                                     │       ▼      │
                                     │ ┌──────────┐│
                                     │ │Warehouse  ││
                                     │ └────┬─────┘│
                                     └───────▶─────┘
                                             │
                                     ┌───────▼──────┐
                                     │Communication │
                                     └──────────────┘
```

**Anti-corruption layers** are placed between:
- Identity → Commerce (role models differ in shape)
- Warehouse → Commerce (inventory model ≠ order model)

---

## 3. Strangler Fig Migration Strategy

### 3.1 Phased Extraction

The **strangler** pattern incrementally replaces the monolith by routing traffic to new services while the monolith continues operating.

#### Phase 1: Foundation (Weeks 1–4)
- [ ] Set up infrastructure (Kubernetes, CI/CD, monitoring)
- [ ] Implement **API gateway** and service mesh
- [ ] Deploy identity service (extract user auth from monolith)
- [ ] Add API gateway routing for `/api/users/**` → identity service

#### Phase 2: Low-Risk Boundaries (Weeks 5–8)
- [ ] Extract Notification service (read-only, independent)
- [ ] Extract Catalog/Search service (read-heavy, simple domain)
- [ ] Route `/api/notifications/**` and `/api/search/**` through gateway
- [ ] Verify monitoring and alerting for extracted services

#### Phase 3: Core Domain Extraction (Weeks 9–16)
- [ ] Extract Inventory service (reservations only)
- [ ] Extract Payment service
- [ ] Deploy **strangler** proxy for `/api/orders/**` to gradually route through new services
- [ ] Implement saga orchestration for order creation flow
- [ ] Double-write to both monolith and new services during transition

#### Phase 4: Remaining Contexts (Weeks 17–20)
- [ ] Extract remaining Order service logic
- [ ] Extract Reporting service (read model)
- [ ] Route all remaining endpoints through gateway
- [ ] Decommission monolith endpoints one by one

### 3.2 Migration Checklist per Service

- [ ] Code extracted and in own repository
- [ ] Independent CI/CD pipeline
- [ ] Own **database per service** (migrated from shared schema)
- [ ] API contracts defined (OpenAPI/Swagger)
- [ ] Health checks and readiness probes
- [ ] Distributed tracing enabled
- [ ] Load testing passed
- [ ] Feature flag to toggle old vs. new path
- [ ] Rollback procedure documented
- [ ] Operations runbook created

---

## 4. Inter-Service Communication

### 4.1 API Gateway

All external traffic routes through a single **API gateway** (e.g., Kong, Apigee, or NGINX):

```
Client → API Gateway → {
    /api/users/*       → User Service
    /api/orders/*      → Order Service
    /api/inventory/*   → Inventory Service
    /api/payments/*    → Payment Service
    /api/notifications/* → Notification Service
    /api/search/*      → Search Service
}
```

**Gateway responsibilities:**
- Authentication/authorization (JWT validation)
- Rate limiting and throttling
- Request/response transformation
- Circuit breaker configuration
- Request routing and load balancing
- SSL termination

### 4.2 Synchronous Communication (REST/gRPC)

Used for real-time request-response patterns:

| Caller | Callee | Protocol | Reason |
|--------|--------|----------|--------|
| Order Service | Inventory Service | gRPC | Low-latency stock check |
| Order Service | Payment Service | REST | Payment initiation |
| Frontend | Any Service | REST (via Gateway) | User-facing requests |

### 4.3 Asynchronous Communication (Event-Driven)

A message queue handles decoupled, eventual-consistency flows:

```
┌──────────┐     events      ┌───────────┐
│ Publisher│─────────────────▶│ Message   │
│ Services │                 │ Queue /   │
└──────────┘                 │ Bus       │
                             └─────┬─────┘
                                   │ subscribe
                         ┌──────────┼──────────┐
                         ▼          ▼          ▼
                   Subscriber  Subscriber  Subscriber
                   Service A   Service B   Service C
```

**Key events:**

| Event | Source | Consumers | Payload |
|-------|--------|-----------|---------|
| `OrderCreated` | Order Service | Payment, Notification | order_id, amount, user_id |
| `PaymentCompleted` | Payment Service | Order, Reporting | order_id, payment_id, amount |
| `StockReserved` | Inventory Service | Order | order_id, product_id, quantity |
| `UserRegistered` | User Service | Notification, Reporting | user_id, email |
| `OrderCancelled` | Order Service | Payment, Inventory, Notification | order_id, reason |

### 4.4 Communication Patterns

- **Saga Pattern**: Coordinate distributed transactions (e.g., Order → Payment → Inventory)
- **CQRS**: Separate read and write models for Reporting/Analytics
- **Event Sourcing**: Consider for Order and Payment domains (audit trail)

---

## 5. Data Migration Strategy

### 5.1 Database per Service

Adopt the **database per service** pattern: each service owns its data store, and no other service can directly query it.

| Service | Database | Rationale |
|---------|----------|-----------|
| User | PostgreSQL | Relational, strong consistency for auth |
| Order | PostgreSQL | Complex queries, relational integrity |
| Inventory | PostgreSQL | Stock accuracy, transactions |
| Payment | PostgreSQL | ACID compliance required |
| Notification | MongoDB | Flexible schema, high write volume |
| Search | Elasticsearch | Full-text search, aggregations |
| Reporting | ClickHouse | Analytical queries, time-series |

### 5.2 Migration Steps

```
Step 1: Schema Design
  → Define new per-service schemas
  → Identify all shared tables in monolith

Step 2: Dual-Write Implementation
  → On write path: write to both old and new databases
  → On read path: read from old database (canonical source)

Step 3: Backfill Historical Data
  → Migrate existing data to new databases
  → Validate data integrity (checksums, row counts)

Step 4: Switch Reads
  → Gradually shift reads to new databases
  → Monitor error rates and latency

Step 5: Stop Dual-Write
  → Once all reads are on new databases, disable dual-write
  → Decommission monolith database tables

Step 6: Decommission Monolith
  → Turn off monolith endpoints via API gateway
  → Archive monolith database for compliance
```

### 5.3 Consistency Strategy

| Data | Consistency Model | Mechanism |
|------|-------------------|-----------|
| User sessions | Strong | Single database, synchronous |
| Order state | Eventual | Event sourcing + outbox pattern |
| Inventory counts | Eventual | Async reservation flow, reconciliation job |
| Payment records | Strong | ACID transactions, synchronous confirmation |
| Notifications | Eventual | Message queue, retry with dead-letter |
| Reports | Eventual | CDC from OLTP databases to analytics store |

### 5.4 Outbox Pattern

To guarantee event delivery:

```
┌──────────────────────────────────┐
│  Service Transaction             │
│  1. Update database              │
│  2. Write event to outbox table  │
│  3. Commit transaction           │
└──────────────────────────────────┘
              │
              ▼ (polling/cdc)
┌──────────────────────────┐
│  Outbox Poller            │
│  Reads unprocessed events │
│  Publishes to message     │
│  queue                    │
└──────────────────────────┘
```

---

## 6. Infrastructure & Operations

### 6.1 Technology Stack

| Component | Recommendation |
|-----------|---------------|
| Container Orchestration | Kubernetes (EKS/GKE) |
| API Gateway | Kong or AWS API Gateway |
| Service Mesh | Istio or Linkerd |
| Message Broker | Apache Kafka or RabbitMQ |
| CI/CD | GitHub Actions or GitLab CI |
| Monitoring | Prometheus + Grafana |
| Tracing | Jaeger or Tempo |
| Secrets | HashiCorp Vault or AWS Secrets Manager |

### 6.2 Key Metrics

- **SLOs**: 99.9% uptime per service, <200ms p95 latency
- **Observability**: Distributed tracing, structured logging, health endpoints
- **Deployment**: Blue-green or canary deployments per service
- **Security**: mTLS between services, RBAC, audit logging

---

## 7. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Distributed transactions failures | High | Saga pattern with compensating actions |
| Data inconsistency during migration | High | Dual-write + reconciliation jobs |
| Latency increase from network calls | Medium | gRPC, connection pooling, caching |
| Operational complexity | High | Standardize on shared libraries, automated runbooks |
| Team coordination overhead | Medium | Domain teams aligned to bounded contexts |

---

## 8. Timeline Summary

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Foundation | 4 weeks | Infra, gateway, identity service |
| Low-Risk Extraction | 4 weeks | Notification + Search services |
| Core Domain | 8 weeks | Order, Payment, Inventory services |
| Remaining | 4 weeks | Reporting, monolith decommission |
| **Total** | **~20 weeks** | **Fully decomposed** |
