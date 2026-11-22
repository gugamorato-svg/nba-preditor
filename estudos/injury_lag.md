# Injury Lag Analysis

## Hypothesis
We want to determine whether Polymarket prices react to injury news before or after it becomes public on ESPN. If the market has already moved before news breaks, then injury news is not an edge. If there is a lag between news and price movement, that lag could represent a trading opportunity.

## Methodology

### Data Sources
- `data/injuries_log.csv`: Contains changes in ESPN's injury list, with the time ESPN updated each entry (`espn_utc`).
- `data/paper_log.csv`: Contains model probability plus Polymarket bid/ask for upcoming games, captured hourly.

### Analysis Steps
1. **Filter for 'Out' injuries**: We only consider players who are ruled out ('Out') as these have the most significant impact on game outcomes.

2. **Find next game**: For each injury, find the team's next scheduled game after the injury update time.

3. **Compare prices**: Look at the Polymarket price for the home team just before and just after the injury update time.

4. **Calculate price change**: Determine if and how much the price moved after the injury news.

### Limitations
- **Data granularity**: Data is captured hourly, so we can only detect lags longer than about an hour.
- **Sample size**: The analysis depends on having both injury data and price data for the same games. The sample may be small initially.
- **Market efficiency**: The analysis doesn't account for other factors that might influence prices (e.g., other news, market sentiment).

### Expected Results
We'll report:
- The number of injuries analyzed with complete data
- Average price change after injury news
- Direction of price movement (increase/decrease/no change)
- Time lag between news and price movement

## Results

*Results will be added after running the analysis script.*
