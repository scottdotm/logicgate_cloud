"""Built-in NIST CSF-aligned security policy templates."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BuiltInPolicy:
    key: str
    title: str
    nist_function: str
    nist_category: str
    content: str


BUILT_IN_POLICIES: list[BuiltInPolicy] = [
    BuiltInPolicy(
        key="acceptable_use",
        title="Acceptable Use Policy",
        nist_function="PR",
        nist_category="Identity Management",
        content="""# Acceptable Use Policy

## Purpose
This policy defines acceptable use of organization information systems and resources.

## Scope
Applies to all employees, contractors, and third-party users.

## Policy
1. Organization resources are to be used primarily for business purposes.
2. Users must not install unauthorized software or hardware.
3. Sensitive data must be transmitted only over approved encrypted channels.
4. Reporting of suspected misuse or security incidents is mandatory.

## Enforcement
Violations may result in disciplinary action up to and including termination.
""",
    ),
    BuiltInPolicy(
        key="password_policy",
        title="Password Policy",
        nist_function="PR",
        nist_category="Identity Management",
        content="""# Password Policy

## Purpose
Protect accounts and systems through strong password practices.

## Policy
1. Passwords must be at least 12 characters long.
2. Passwords must contain a mix of uppercase, lowercase, numbers, and symbols.
3. Passwords must not be reused across systems or shared with others.
4. Multi-factor authentication must be enabled where available.
5. Passwords must be changed immediately if compromise is suspected.

## Tools
A business password manager is required for storing and sharing credentials.
""",
    ),
    BuiltInPolicy(
        key="mfa_policy",
        title="Multi-Factor Authentication Policy",
        nist_function="PR",
        nist_category="Access Control",
        content="""# Multi-Factor Authentication Policy

## Purpose
Reduce account takeover risk by requiring additional verification.

## Policy
1. MFA is required for all cloud/email, remote access, and financial systems.
2. SMS-based MFA is discouraged; authenticator apps or hardware keys are preferred.
3. New user onboarding includes MFA enrollment.
4. Exceptions require documented approval from leadership.

## Responsibilities
IT ensures MFA is enforced organization-wide and reviewed quarterly.
""",
    ),
    BuiltInPolicy(
        key="incident_response",
        title="Incident Response Plan",
        nist_function="RS",
        nist_category="Response Planning",
        content="""# Incident Response Plan

## Purpose
Provide a structured approach to detecting, responding to, and recovering from cybersecurity incidents.

## Roles
- Incident Lead: coordinates response and communications.
- IT Support: contains affected systems and preserves evidence.
- Legal/HR: advises on regulatory and personnel matters.

## Phases
1. Detection and reporting
2. Containment
3. Eradication
4. Recovery
5. Post-incident review

## Contact
Report incidents to the designated security contact immediately.
""",
    ),
    BuiltInPolicy(
        key="remote_access",
        title="Remote Access Policy",
        nist_function="PR",
        nist_category="Access Control",
        content="""# Remote Access Policy

## Purpose
Secure remote access to organization systems and data.

## Policy
1. Remote access is permitted only through approved VPN or Zero Trust solutions.
2. MFA is required for all remote access.
3. Remote sessions must use organization-managed devices.
4. Personal devices may not be used for remote access unless enrolled in MDM.

## Monitoring
Remote access sessions are logged and reviewed periodically.
""",
    ),
    BuiltInPolicy(
        key="byod_policy",
        title="Bring Your Own Device Policy",
        nist_function="PR",
        nist_category="Access Control",
        content="""# Bring Your Own Device (BYOD) Policy

## Purpose
Define requirements for personal devices that access organization data.

## Policy
1. BYOD devices must be registered and enrolled in mobile device management.
2. Devices must use a passcode or biometric lock.
3. Organization data must be stored in approved apps; local copies are discouraged.
4. Lost or stolen devices must be reported within 24 hours.

## Separation
Organization data may be remotely wiped from registered devices upon termination or loss.
""",
    ),
    BuiltInPolicy(
        key="data_retention",
        title="Data Retention and Disposal Policy",
        nist_function="PR",
        nist_category="Data Security",
        content="""# Data Retention and Disposal Policy

## Purpose
Retain data for required periods and dispose of it securely when no longer needed.

## Policy
1. Data retention periods follow legal, regulatory, and business requirements.
2. Sensitive data is encrypted at rest and in transit.
3. Data disposal uses secure deletion methods.
4. Backup retention is defined separately and tested periodically.

## Responsibilities
Data owners classify data and approve retention schedules.
""",
    ),
    BuiltInPolicy(
        key="vendor_management",
        title="Vendor Management Policy",
        nist_function="GV",
        nist_category="Cybersecurity Risk Management Strategy",
        content="""# Vendor Management Policy

## Purpose
Manage cybersecurity risks introduced by third-party vendors and service providers.

## Policy
1. Vendors with access to sensitive data are assessed for security posture.
2. Contracts include confidentiality and security requirements.
3. Vendor access is reviewed and revoked promptly when no longer needed.
4. Critical vendors are reviewed at least annually.

## Responsibilities
Procurement and IT coordinate vendor security reviews.
""",
    ),
    BuiltInPolicy(
        key="backup_recovery",
        title="Backup and Recovery Policy",
        nist_function="RC",
        nist_category="Recovery Planning",
        content="""# Backup and Recovery Policy

## Purpose
Ensure critical data and systems can be recovered after disruption.

## Policy
1. Critical data is backed up at least daily.
2. Backups are stored offsite or in immutable cloud storage.
3. Recovery procedures are documented and tested at least annually.
4. Backup encryption is required for sensitive data.

## Responsibilities
IT owns backup configuration, monitoring, and recovery testing.
""",
    ),
    BuiltInPolicy(
        key="acceptable_encryption",
        title="Acceptable Encryption Policy",
        nist_function="PR",
        nist_category="Data Security",
        content="""# Acceptable Encryption Policy

## Purpose
Define approved encryption standards for data at rest and in transit.

## Policy
1. Data in transit must use TLS 1.2 or higher.
2. Data at rest must use AES-256 or equivalent.
3. Key management is centralized and access is restricted.
4. Legacy encryption algorithms (MD5, SHA-1, DES) are prohibited.

## Compliance
Encryption practices are reviewed during risk assessments and audits.
""",
    ),
]

BUILT_IN_POLICY_INDEX: dict[str, BuiltInPolicy] = {p.key: p for p in BUILT_IN_POLICIES}
