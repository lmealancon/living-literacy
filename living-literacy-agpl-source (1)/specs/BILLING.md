# Billing and entitlement specification — draft

Plans: Free ($0), Family Plus ($9.99/month), Solo Educator ($19.99/month). Institutional licensing custom TBD. No annual plan price approved. Solo Educator learner limit unresolved.

Use approved third-party payment processor; never store raw card details. Verify webhook authenticity; idempotent event processing; server-authoritative entitlement state. Support trial/active/past_due/canceled/unpaid/paused/expired as applicable to selected provider. Transparent renewals, cancellation, refunds and access changes per applicable law.

Canceling a subscription is separate from deleting student records. Free instruction, privacy controls, accessibility and validity rules cannot be paywalled or bypassed. Student-data authority is independent of billing.
