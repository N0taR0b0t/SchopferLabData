library(dplyr)
library(stringr)

score1 <- read.csv("score1.csv")
score2 <- read.csv("score2.csv")
score3 <- read.csv("score3.csv")

# Combine top 100 entries from each based on scores
top_scores <- bind_rows(
  score1 %>% arrange(desc(Score1)) %>% head(200),
  score2 %>% arrange(desc(Score2)) %>% head(200),
  score3 %>% arrange(desc(Score3)) %>% head(200)
) %>% distinct(Name, .keep_all = TRUE)  # Ensure no duplicates

# Function to extract meaningful endings, capturing important chemical suffixes
extract_ending <- function(name) {
  # Define pattern to capture relevant chemical suffixes with preceding word characters
  pattern <- "\\b[[:alnum:]]{3,}( acid| base|ate|ide|one|ol|ene|yne|diol|ic acid|amide|ium|in|al)$"
  ending <- str_extract(name, pattern)
  if (!is.na(ending)) {
    ending <- trimws(ending)
  }
  ending
}

# Apply the function to find similar compounds by their endings
top_scores$Ending <- sapply(top_scores$Name, extract_ending)

# Remove entries without a valid ending
top_scores <- top_scores %>% filter(!is.na(Ending))

# Group by the extracted endings to find similarities
similar_compounds <- top_scores %>%
  group_by(Ending) %>%
  summarize(Compounds = toString(unique(Name)), Count = n(), .groups = 'drop') %>%
  filter(Count > 1)  # Exclude groups with only one compound

# Order by Count descending
similar_compounds <- similar_compounds %>% arrange(desc(Count))

write.csv(similar_compounds, "similar_compounds.csv", row.names = FALSE)

# Set options to avoid truncation
options(width = 1000, max.print = 1000000)

# Print out some of the similar compounds grouped by their endings
print(similar_compounds)
