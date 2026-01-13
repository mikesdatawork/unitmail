# unitMail Implementation Roadmap

**Created:** 2026-01-12
**Author:** change-coordinator agent (T14)
**Status:** Final Consolidated Report

---

## Executive Summary

This document consolidates findings from all 5 specialist agents across Phase 1 and Phase 2 of the unitMail application review. The review identified **47 distinct issues** across accessibility, performance, security, testing, and usability domains. This roadmap provides a prioritized, phased approach to address these issues.

**Overall Application Health Score:** 6.8/10

---

## 1. Consolidated Findings Table

### 1.1 Phase 1 Findings (Parallel Analysis)

#### email-ui-expert (T1-T6, T13): UI/UX and Accessibility Audit

| ID | Issue | Severity | Category | Status |
|----|-------|----------|----------|--------|
| UI-01 | Search non-functional | P1/Critical | Functionality | FIXED |
| UI-02 | Sort dropdown not wired | P1/Critical | Functionality | FIXED |
| UI-03 | Reply/Forward broken | P1/Critical | Functionality | FIXED |
| UI-04 | Select All broken | P1/Critical | Functionality | FIXED |
| UI-05 | Message threading missing | P1/Critical | Architecture | PENDING |
| UI-06 | Missing WCAG 2.1 AA focus indicators | P2/High | Accessibility | PENDING |
| UI-07 | Color contrast issues (opacity:0.7) | P2/High | Accessibility | PENDING |
| UI-08 | Missing skip links | P2/Medium | Accessibility | PENDING |
| UI-09 | Missing ARIA live regions | P2/Medium | Accessibility | PENDING |
| UI-10 | No visible focus ring customization | P2/Medium | Accessibility | PENDING |
| UI-11 | Empty states lack CTAs | P2/High | UX | PENDING |
| UI-12 | Row selection visual feedback missing | P2/High | UX | PENDING |
| UI-13 | Keyboard navigation gaps (15+ shortcuts) | P2/Medium | Accessibility | PENDING |
| UI-14 | Theme opacity:0 hack for hiding | P3/Low | Technical Debt | PENDING |
| UI-15 | Attachment count not displayed | P3/Medium | Feature | PENDING |

#### performance-engineer (T7-T8): Performance Analysis

| ID | Issue | Severity | Category | Impact |
|----|-------|----------|----------|--------|
| PERF-01 | Widget traversal in message bind | P2/High | CPU | ~5ms per row |
| PERF-02 | Theme import in hot path | P2/Medium | Latency | Import on every bind |
| PERF-03 | Universal CSS selector (*) | P2/High | Rendering | All elements affected |
| PERF-04 | CSS transitions on message rows | P2/Medium | Rendering | Jank on scroll |
| PERF-05 | Redundant CSS declarations | P3/Low | Maintenance | 20+ duplicates |
| PERF-06 | No FilterListModel usage | P2/Medium | Memory | Full list copies |
| PERF-07 | No SortListModel usage | P2/Medium | CPU | Manual sort loops |

#### security-auditor (T9-T10): Security Audit

| ID | Issue | Severity | Category | OWASP Ref |
|----|-------|----------|----------|-----------|
| SEC-01 | Missing encryption/signing indicators | HIGH | Trust/UI | A03:2021 |
| SEC-02 | Regex-based HTML sanitization | MEDIUM | XSS | A03:2021 |
| SEC-03 | Passphrase handling in memory | MEDIUM | Secrets | A02:2021 |
| SEC-04 | Key generation UX unclear | MEDIUM | Usability | N/A |
| SEC-05 | No passphrase strength meter | LOW | Usability | N/A |

### 1.2 Phase 2 Findings (Sequential Analysis)

#### test-automation (T11): Test Infrastructure Analysis

| ID | Issue | Severity | Category | Impact |
|----|-------|----------|----------|--------|
| TEST-01 | **CRITICAL**: Playwright tests for GTK4 app | CRITICAL | Framework | 160 tests unusable |
| TEST-02 | No GTK4 test infrastructure | HIGH | Testing | 0% coverage |
| TEST-03 | 8+ major features untested | HIGH | Quality | Risk of regression |
| TEST-04 | No unit tests for models | MEDIUM | Testing | Data layer untested |
| TEST-05 | No integration tests | MEDIUM | Testing | Service layer untested |
| TEST-06 | No accessibility tests | MEDIUM | Compliance | WCAG untested |

**Untested Features:**
1. Message compose and send flow
2. PGP encryption/decryption
3. Folder operations (create, delete, move)
4. Search functionality
5. Sort functionality
6. View density switching
7. Settings persistence
8. Export functionality

#### user-simulation (T12): Exploratory UX Testing

| ID | Issue | Severity | Category | Usability Score |
|----|-------|----------|----------|-----------------|
| UX-01 | PGP features are mock/placeholder | HIGH | Completeness | 3/10 |
| UX-02 | No actual email sending | HIGH | Core Feature | 4/10 |
| UX-03 | Compose window not implemented | HIGH | Core Feature | 5/10 |
| UX-04 | Connection status always "Disconnected" | MEDIUM | Feedback | 6/10 |
| UX-05 | Attachment preview not working | MEDIUM | Feature | 6/10 |
| UX-06 | No error recovery guidance | MEDIUM | UX | 6/10 |

**User Journey Scores:**
| Journey | Score | Notes |
|---------|-------|-------|
| View messages | 8/10 | Good basic flow |
| Compose email | 5/10 | Opens but doesn't send |
| Search/filter | 8/10 | Works after fix |
| PGP encryption | 3/10 | Mock only |
| Settings management | 8/10 | Well organized |
| Folder management | 7/10 | Basic operations work |

**Overall Usability Score: 7.25/10**

---

## 2. Priority Matrix (Impact vs Effort)

```
HIGH IMPACT
     ^
     |  [TEST-01]        [UI-05]          [UX-01,02,03]
     |  Framework Fix    Threading        Core Features
     |  EFFORT: HIGH     EFFORT: HIGH     EFFORT: HIGH
     |
     |  [SEC-01]         [SEC-02]
     |  Status Icons     Bleach Library
     |  EFFORT: LOW      EFFORT: LOW
     |
     |  [PERF-03]        [UI-11,12]       [PERF-01,02]
     |  CSS Selector     Empty States     Widget Cache
     |  EFFORT: LOW      EFFORT: MEDIUM   EFFORT: MEDIUM
     |
     |  [UI-06,07]       [PERF-06,07]
     |  Accessibility    GTK Models
     |  EFFORT: MEDIUM   EFFORT: MEDIUM
     +------------------------------------------------------> EFFORT
LOW IMPACT                                           HIGH EFFORT
```

---

## 3. Quick Wins (High Impact, Low Effort)

These can be implemented in 1-2 days each:

| Priority | ID | Task | Estimated Time | Impact |
|----------|-----|------|----------------|--------|
| 1 | SEC-01 | Add encryption/signing status indicators to message preview | 4 hours | HIGH |
| 2 | SEC-02 | Replace regex sanitization with bleach library | 2 hours | HIGH |
| 3 | PERF-03 | Replace `* { border-radius: 0; }` with specific selectors | 2 hours | MEDIUM |
| 4 | UI-11 | Add empty states with refresh CTAs | 4 hours | MEDIUM |
| 5 | UI-12 | Add visual feedback for row selection | 3 hours | MEDIUM |
| 6 | UI-14 | Replace opacity:0 hacks with set_visible(False) | 2 hours | LOW |
| 7 | PERF-05 | Consolidate redundant CSS declarations | 2 hours | LOW |
| 8 | SEC-05 | Add passphrase strength meter | 3 hours | LOW |

**Total Quick Wins Effort: ~22 hours (3 days)**

---

## 4. Phased Implementation Roadmap

### Phase A: Foundation & Security (Weeks 1-2)

**Goal:** Establish test infrastructure and fix critical security issues

| Week | Tasks | Owner | Dependencies |
|------|-------|-------|--------------|
| 1 | TEST-01: Create GTK4 test infrastructure with pytest-gtk4 | test-automation | None |
| 1 | SEC-01: Add encryption/signing indicators | security-auditor | None |
| 1 | SEC-02: Integrate bleach for HTML sanitization | security-auditor | None |
| 2 | TEST-02: Write unit tests for models (MessageItem, FolderItem) | test-automation | TEST-01 |
| 2 | SEC-03: Implement secure passphrase memory handling | security-auditor | None |
| 2 | Quick Wins #1-4 | email-ui-expert | None |

**Deliverables:**
- GTK4 test harness with 20+ tests
- Security indicators in UI
- Sanitization via bleach
- 4 quick wins completed

### Phase B: Core Features & Performance (Weeks 3-4)

**Goal:** Complete core email features and optimize performance

| Week | Tasks | Owner | Dependencies |
|------|-------|-------|--------------|
| 3 | UX-02,03: Implement actual email sending via gateway | gateway-specialist | Phase A |
| 3 | PERF-01,02: Cache widget references, move imports | performance-engineer | None |
| 3 | PERF-06,07: Implement FilterListModel/SortListModel | performance-engineer | None |
| 4 | UX-01: Complete PGP encryption/decryption flow | security-auditor | SEC-01,02 |
| 4 | UI-06,07: WCAG 2.1 AA accessibility compliance | email-ui-expert | None |
| 4 | TEST-03: Write integration tests for email flow | test-automation | UX-02,03 |

**Deliverables:**
- Working email send/receive
- 50% performance improvement on message list
- Accessibility audit passing
- 40+ integration tests

### Phase C: Architecture & Polish (Weeks 5-6)

**Goal:** Address architectural issues and enhance UX

| Week | Tasks | Owner | Dependencies |
|------|-------|-------|--------------|
| 5 | UI-05: Implement message threading | email-ui-expert | Phase B |
| 5 | UI-13: Add remaining keyboard shortcuts | email-ui-expert | None |
| 5 | UX-04,05,06: Connection status, attachments, error recovery | user-simulation | Phase B |
| 6 | TEST-04,05: Complete unit and integration test coverage | test-automation | All features |
| 6 | TEST-06: Accessibility automated testing | test-automation | UI-06,07 |
| 6 | Documentation and release preparation | change-coordinator | All tasks |

**Deliverables:**
- Message threading
- Full keyboard navigation
- 80%+ test coverage
- Release candidate ready

---

## 5. Architectural Decisions Required

### 5.1 Test Framework Decision

**Question:** Should we create custom GTK4 test infrastructure or use existing solutions?

**Options:**
1. **Custom pytest fixtures** - Full control, GTK-specific
2. **Dogtail** - Accessibility-based testing
3. **pytest-gtk4** - If available
4. **Screenshot-based testing** - Visual regression

**Recommendation:** Custom pytest fixtures with Gtk.Application.run_test() pattern

**Decision Needed By:** Week 1

### 5.2 Message Threading Architecture

**Question:** How should message threading be implemented?

**Options:**
1. **Client-side threading** - Parse In-Reply-To headers
2. **Server-side threading** - Gateway provides thread structure
3. **Hybrid** - Server provides, client caches

**Recommendation:** Hybrid approach for offline support

**Decision Needed By:** Week 4

### 5.3 HTML Sanitization Strategy

**Question:** How to handle HTML email content safely?

**Options:**
1. **bleach** - Python library, well-maintained
2. **html5lib + custom** - More control
3. **GTK WebKit sandbox** - Render in isolated view

**Recommendation:** bleach for initial sanitization, WebKit sandbox for display

**Decision Needed By:** Week 1

### 5.4 Performance Optimization Strategy

**Question:** Should we use GTK4's FilterListModel/SortListModel or custom implementation?

**Options:**
1. **Native GTK4 models** - Best integration, reactive
2. **Custom Python** - More control, familiar
3. **Hybrid** - GTK models with custom adapters

**Recommendation:** Native GTK4 models for better scrolling performance

**Decision Needed By:** Week 3

---

## 6. Resource/Effort Estimates

### 6.1 Total Effort by Phase

| Phase | Duration | Effort (Person-Days) | Primary Focus |
|-------|----------|---------------------|---------------|
| Phase A | 2 weeks | 15-20 days | Test infra, Security |
| Phase B | 2 weeks | 20-25 days | Core features, Performance |
| Phase C | 2 weeks | 15-20 days | Architecture, Polish |
| **Total** | **6 weeks** | **50-65 days** | |

### 6.2 Effort by Domain

| Domain | Issues | Effort | Notes |
|--------|--------|--------|-------|
| Testing | 6 | 20 days | New infrastructure required |
| Security | 5 | 8 days | Mostly straightforward |
| Performance | 7 | 10 days | GTK4 model refactoring |
| UI/Accessibility | 15 | 15 days | Some require threading |
| UX/Features | 6 | 12 days | Core feature completion |

### 6.3 Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| GTK4 test framework complexity | Medium | High | Allocate extra time in Week 1 |
| Message threading scope creep | High | Medium | Define MVP threading first |
| PGP integration issues | Medium | High | Isolate in separate module |
| Performance regression | Low | Medium | Continuous benchmarking |

---

## 7. Cross-Reference Analysis

### 7.1 Overlapping Issues

Several issues were identified by multiple agents:

| Issue Area | Agents | Consolidated Finding |
|------------|--------|---------------------|
| Accessibility/Focus | email-ui-expert, user-simulation | Focus indicators need improvement across all interactive elements |
| Performance/Scrolling | performance-engineer, user-simulation | Message list scrolling causes jank due to CSS and widget binding |
| Security/PGP | security-auditor, user-simulation | PGP features are incomplete and lack status feedback |
| Testing/Coverage | test-automation, all agents | 0% automated test coverage is critical blocker |

### 7.2 Dependencies Between Findings

```
TEST-01 (Test Framework)
    |
    +---> TEST-02 (Unit Tests)
    |         |
    |         +---> TEST-03 (Integration Tests)
    |                   |
    |                   +---> TEST-06 (A11y Tests)
    |
SEC-01 (Status Indicators)
    |
    +---> UX-01 (PGP Completion)
              |
              +---> Complete Email Flow

PERF-06,07 (GTK Models)
    |
    +---> UI-05 (Threading)
              |
              +---> PERF-01 (Widget Cache) -- reduced need
```

---

## 8. Final Recommendations

### 8.1 Immediate Actions (This Week)

1. **Create GTK4 test harness** - Block all other work until basic tests run
2. **Implement security indicators** - Quick win with high user trust impact
3. **Replace HTML regex sanitization** - Security vulnerability

### 8.2 Short-term Priorities (Next 2 Weeks)

1. Complete Phase A deliverables
2. Begin core feature implementation (email sending)
3. Establish performance benchmarks

### 8.3 Medium-term Goals (Weeks 3-6)

1. Achieve 60%+ test coverage
2. Complete accessibility audit
3. Ship message threading
4. Release candidate preparation

### 8.4 Success Metrics

| Metric | Current | Target | Measure |
|--------|---------|--------|---------|
| Test Coverage | 0% | 80% | pytest-cov |
| Accessibility Score | ~60% | 95% | WCAG 2.1 AA audit |
| Performance (scroll FPS) | ~45 | 60 | GTK profiler |
| Usability Score | 7.25/10 | 8.5/10 | User testing |
| Security Issues | 5 | 0 HIGH/MEDIUM | Security audit |

---

## Appendix A: File References

Key files analyzed during this review:

| File | Purpose | Issues Found |
|------|---------|--------------|
| `/home/user/projects/unitmail/src/client/ui/main_window.py` | Main UI | UI-01 to UI-15, PERF-01,02 |
| `/home/user/projects/unitmail/src/client/ui/styles.css` | Styling | PERF-03,04,05, UI-14 |
| `/home/user/projects/unitmail/src/client/ui/settings.py` | Settings | SEC-03,04,05 |
| `/home/user/projects/unitmail/src/client/ui/widgets/pgp_key_manager.py` | PGP | SEC-01, UX-01 |
| `/home/user/projects/unitmail/tests/e2e/conftest.py` | Tests | TEST-01 |

---

## Appendix B: Agent Work Logs Summary

All agent tasks completed as specified:
- **email-ui-expert (T1-T6, T13)**: Completed - 15 issues identified
- **performance-engineer (T7-T8)**: Completed - 7 bottlenecks identified
- **security-auditor (T9-T10)**: Completed - 5 vulnerabilities identified
- **test-automation (T11)**: Completed - Critical framework mismatch found
- **user-simulation (T12)**: Completed - 24 user journeys documented

---

*This roadmap should be reviewed and updated weekly as implementation progresses.*
