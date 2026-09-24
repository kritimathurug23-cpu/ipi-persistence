# Primary preregistered model (proposal Section 27.2).
#   Rscript analysis/glmer.R runs/main/analysis/turns.csv
# install.packages(c("lme4", "emmeans"))
#
# IMPORTANT DESIGN NOTE (found when testing this pipeline):
# P4 (full rollback) is expected to show ~0% attacker markers by construction. Using it as a
# level in the logistic model causes complete separation and meaningless estimates. So:
#   * this model compares the persistence conditions P1-P3 (reference = P2, redacted);
#   * "does P2/P3 exceed the noise floor?" is tested with the exact McNemar tests against P4
#     in analysis/analyze.py, which handle zero cells correctly.
# State this split explicitly in the preregistration.
library(lme4)
library(emmeans)

args <- commandArgs(trailingOnly = TRUE)
path <- ifelse(length(args) > 0, args[1], "runs/main/analysis/turns.csv")
d <- read.csv(path)
d$marker <- as.integer(d$marker == "True" | d$marker == TRUE)
d <- d[d$condition %in% c("P1", "P2", "P3"), ]
d$condition <- relevel(factor(d$condition), ref = "P2")
d$source <- factor(d$source)
d$task_type <- factor(d$task_type)

fit <- function(formula) {
  glmer(formula, data = d, family = binomial,
        control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5)))
}

# Main model: condition x turn, random intercept per compromised state.
# If there are enough states per model, add (1 | model) as preregistered.
m <- fit(marker ~ condition * turn + task_type + source + (1 | state_id))
print(summary(m))

# If lme4 reports singular fits or non-convergence, report it and refit without the interaction.
if (isSingular(m) || length(m@optinfo$conv$lme4$messages) > 0) {
  cat("\n[note] convergence/singularity issue: refitting without condition x turn interaction\n")
  m <- fit(marker ~ condition + turn + task_type + source + (1 | state_id))
  print(summary(m))
}

for (t in c(1, 3)) {
  cat("\n=== Condition contrasts at turn", t, "(odds ratios, Holm-adjusted) ===\n")
  em <- emmeans(m, ~ condition, at = list(turn = t), type = "response")
  print(pairs(em, adjust = "holm"))
}
