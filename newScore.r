library(shiny)
library(dplyr)
library(data.table)
library(DT)

# Define default safe values for sliders
default_min_peak <- 0
default_max_peak <- 100
default_min_pvalue <- -10
default_max_pvalue <- 0
default_min_log2fc <- -2
default_max_log2fc <- 2

# Function to safely get min and max for sliders
safe_range <- function(data_column, log_scale = FALSE) {
  if (length(data_column) == 0 || all(is.na(data_column))) {
    message("Data column is empty or all NA.")
    return(c(0, 1))  # Return a default range if no valid data
  }

  if (log_scale) {
    data_column <- log10(data_column)
    if (any(is.nan(data_column), na.rm = TRUE)) {
      message("Warning: NaN values produced after log transformation.")
    }
    data_column <- na.omit(data_column)
    data_column <- data_column[!is.infinite(data_column)]
  }

  valid_data <- na.omit(data_column)
  valid_data <- valid_data[!is.nan(valid_data)]
  valid_data <- valid_data[!is.infinite(valid_data)]

  if (length(valid_data) == 0) {
    message("No valid data available after cleaning. Using default range.")
    return(c(0, 1))
  }

  range(valid_data)
}

# Load default data with comprehensive checks
print("Loading default data...")
default_data_path <- "Compounds.csv"
default_data <- tryCatch({
  data <- fread(default_data_path)
  # Calculate safe ranges for sliders
  list(
    peak = safe_range(data$`Peak Rating (Max.)`),
    pvalue = safe_range(data$`Adj. P-value: (cla-no2) / (ctrol)`, log_scale = TRUE),
    log2fc = safe_range(data$`Log2 Fold Change: (cla-no2) / (ctrol)`),
    data = data
  )
}, error = function(e) {
  message("Error loading default data: ", e$message)
  list(peak = c(default_min_peak, default_max_peak), pvalue = c(default_min_pvalue, default_max_pvalue), log2fc = c(default_min_log2fc, default_max_log2fc), data = data.table())  # Safe defaults
})

# Define UI
ui <- fluidPage(
  tags$style(type="text/css", "table { white-space: nowrap; }"),  # CSS to prevent text wrapping
  titlePanel("Compound Scoring System"),
  sidebarLayout(
    sidebarPanel(
      fileInput("file", "Choose CSV File (default is Compounds.csv)", accept = ".csv"),
      tags$p("Default data loaded if no file selected."),
      sliderInput("peakRatingRange", "Peak Rating:", min = default_data$peak[1], max = default_data$peak[2], value = default_data$peak),
      sliderInput("pValueRange", "Adjusted P-value (Log Scale):", min = floor(default_data$pvalue[1]), max = ceiling(default_data$pvalue[2]), value = c(floor(default_data$pvalue[1]), ceiling(default_data$pvalue[2])), step = 1),
      sliderInput("log2ChangeRange", "Log2 Fold Change (Log Scale):", min = floor(default_data$log2fc[1]), max = ceiling(default_data$log2fc[2]), value = c(floor(default_data$log2fc[1]), ceiling(default_data$log2fc[2])), step = 1)
    ),
    mainPanel(
      h3("Positive Fold Changes"),
      DTOutput("table_positive"),
      h3("Negative Fold Changes"),
      DTOutput("table_negative")
    )
  )
)

server <- function(input, output, session) {
  # Reactive for reading data based on user input or default file
  data <- reactive({
    inFile <- input$file
    if (is.null(inFile)) {
      return(fread(default_data_path))
    } else {
      return(fread(inFile$datapath))
    }
  })

  # Observe for file upload and react accordingly
  observe({
    req(data())  # Ensure data is loaded
    
    # Perform calculations
    processed_data <- data() %>%
      mutate(
        Score1 = (1 / `Adj. P-value: (cla-no2) / (ctrol)`) * abs(log2(`Log2 Fold Change: (cla-no2) / (ctrol)`)),
        Score2 = -log10(`Adj. P-value: (cla-no2) / (ctrol)`) + abs(log2(`Log2 Fold Change: (cla-no2) / (ctrol)`)),
        Score3 = 2 * -log10(`Adj. P-value: (cla-no2) / (ctrol)`) + abs(log2(`Log2 Fold Change: (cla-no2) / (ctrol)`))
      ) %>%
      filter(
        `Peak Rating (Max.)` >= input$peakRatingRange[1] & `Peak Rating (Max.)` <= input$peakRatingRange[2],
        `Adj. P-value: (cla-no2) / (ctrol)` >= 10^input$pValueRange[1] & `Adj. P-value: (cla-no2) / (ctrol)` <= 10^input$pValueRange[2],
        `Log2 Fold Change: (cla-no2) / (ctrol)` >= 10^input$log2ChangeRange[1] & `Log2 Fold Change: (cla-no2) / (ctrol)` <= 10^input$log2ChangeRange[2]
      )

    # Separate the data for each score
    score1_data <- processed_data %>%
      select(`Compounds ID`, Score1, Name, Formula)

    score2_data <- processed_data %>%
      select(`Compounds ID`, Score2, Name, Formula)

    score3_data <- processed_data %>%
      select(`Compounds ID`, Score3, Name, Formula)

    # Writing to files (you can add conditions to write only on specific actions)
    write.csv(score1_data, "score1.csv", row.names = FALSE)
    write.csv(score2_data, "score2.csv", row.names = FALSE)
    write.csv(score3_data, "score3.csv", row.names = FALSE)
  })

  # Setup for DataTable outputs
  output$table_positive <- renderDT({
    req(data())
    datatable(data()[data()$`Log2 Fold Change: (cla-no2) / (ctrol)` > 0, ])
})

output$table_negative <- renderDT({
  req(data())
  datatable(data()[data()$`Log2 Fold Change: (cla-no2) / (ctrol)` < 0, ])
  })
}

shinyApp(ui = ui, server = server, options = list(port = 8080))