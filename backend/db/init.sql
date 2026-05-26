-- Smart-Claims Agent — Schema inicial
-- MariaDB 11.3

SET NAMES utf8mb4;
SET time_zone = '+00:00';

-- ── Expedients ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS claims (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    client_id       VARCHAR(64)     NOT NULL,
    claim_type      VARCHAR(64)     NOT NULL,
    channel         ENUM('email','web','whatsapp') NOT NULL DEFAULT 'email',
    status          ENUM(
        'open','validating','extracting','checking_policy',
        'checking_fraud','resolved','rejected','pending_review','closed'
    ) NOT NULL DEFAULT 'open',
    amount_requested DECIMAL(10,2)  NULL,
    amount_approved  DECIMAL(10,2)  NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_client (client_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Log de decisions dels agents ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_decisions (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    claim_id        VARCHAR(36)     NOT NULL,
    agent           VARCHAR(32)     NOT NULL,
    action          VARCHAR(128)    NOT NULL,
    reasoning       TEXT            NOT NULL,
    confidence      FLOAT           NULL,
    hitl_required   BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE CASCADE,
    INDEX idx_claim (claim_id),
    INDEX idx_agent (agent)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Feedback HITL (Human-in-the-Loop) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS hitl_feedback (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    claim_id        VARCHAR(36)     NOT NULL,
    decision_id     BIGINT UNSIGNED NOT NULL,
    reviewer        VARCHAR(128)    NOT NULL,
    original_action VARCHAR(128)    NOT NULL,
    final_action    VARCHAR(128)    NOT NULL,
    override_reason TEXT            NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (claim_id)    REFERENCES claims(id) ON DELETE CASCADE,
    FOREIGN KEY (decision_id) REFERENCES agent_decisions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Seed: expedients de demo ──────────────────────────────────────────────
INSERT IGNORE INTO claims (id, client_id, claim_type, channel, status, amount_requested) VALUES
('CLM-001', 'CLIENT-A', 'danys_propis',    'email',    'open', 3200.00),
('CLM-002', 'CLIENT-B', 'responsabilitat', 'web',      'open', 8500.00),
('CLM-003', 'CLIENT-C', 'robatori',        'whatsapp', 'open', 6000.00);
