"""DataBrokerScanner — consent-based personal privacy self-audit.

Finds where a person's publicly available data appears on people-search and
data-broker sites and surfaces the corresponding opt-out processes.

Scope guarantees (enforced by design, not just documented):
- No login automation.
- No CAPTCHA solving and no bot-detection circumvention.
- Only publicly accessible information is collected.
- Sites that disallow automation (robots.txt/ToS) are handled in an
  assisted, human-in-the-loop mode or as opt-out links only.
"""

__version__ = "0.1.0"
