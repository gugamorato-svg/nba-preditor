#!/usr/bin/env python3
"""Analyze the time lag between Polymarket price movements and injury news updates.

This script reads 'Out' entries from data/injuries_log.csv, finds each team's next game
in data/paper_log.csv, and compares Polymarket prices before and after the espn_utc timestamp.

Usage:
  python estudos/injury_lag.py
"""
import csv
import sys
from datetime import datetime, timezone, timedelta

def parse_utc_timestamp(timestamp_str):
    """Parse a UTC timestamp string into a datetime object."""
    return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

def find_next_game(paper_log, team, injury_time):
    """Find the next game for a team after an injury update."""
    next_game = None
    min_time_diff = None
    
    for row in paper_log:
        if row['home'] == team or row['away'] == team:
            game_time = parse_utc_timestamp(row['game_start'])
            if game_time > injury_time:
                time_diff = (game_time - injury_time).total_seconds() / 3600  # hours
                if min_time_diff is None or time_diff < min_time_diff:
                    min_time_diff = time_diff
                    next_game = row
    
    return next_game

def get_prices_around_time(paper_log, game_id, target_time, hours_before=1, hours_after=1):
    """Get prices before and after a specific time for a game."""
    before_price = None
    after_price = None
    
    for row in paper_log:
        if row['game_id'] == game_id:
            row_time = parse_utc_timestamp(row['paper_utc'])
            
            # Check if this row is within the time window
            time_diff = (row_time - target_time).total_seconds() / 3600  # hours
            
            if -hours_before <= time_diff <= hours_after:
                # Before the target time
                if time_diff < 0 and (before_price is None or time_diff > (parse_utc_timestamp(before_price['paper_utc']) - target_time).total_seconds() / 3600):
                    before_price = row
                # After the target time
                if time_diff > 0 and (after_price is None or time_diff < (parse_utc_timestamp(after_price['paper_utc']) - target_time).total_seconds() / 3600):
                    after_price = row
    
    return before_price, after_price

def main():
    # Load data
    try:
        with open('data/injuries_log.csv', 'r', encoding='utf-8') as f:
            injuries = list(csv.DictReader(f))
    except FileNotFoundError:
        print("Error: data/injuries_log.csv not found. Run paper_collect.py first.")
        sys.exit(1)
    
    try:
        with open('data/paper_log.csv', 'r', encoding='utf-8') as f:
            paper_log = list(csv.DictReader(f))
    except FileNotFoundError:
        print("Error: data/paper_log.csv not found. Run paper_collect.py first.")
        sys.exit(1)
    
    # Filter for 'Out' injuries
    out_injuries = [injury for injury in injuries if injury['status'] == 'Out']
    
    if not out_injuries:
        print("No 'Out' injuries found in injuries_log.csv.")
        return
    
    if not paper_log:
        print("No data found in paper_log.csv.")
        return
    
    print(f"Analyzing {len(out_injuries)} 'Out' injuries...")
    print(f"Paper log contains {len(paper_log)} entries.")
    print("\nNote: Data is captured hourly, so we can only detect lags longer than about an hour.\n")
    
    results = []
    
    for injury in out_injuries:
        try:
            injury_time = parse_utc_timestamp(injury['espn_utc'])
            team = injury['team']
            player = injury['player']
            
            print(f"\nAnalyzing injury: {player} ({team}) at {injury_time}")
            
            next_game = find_next_game(paper_log, team, injury_time)
            
            if not next_game:
                print(f"  No upcoming game found for {team} after injury time.")
                continue
            
            print(f"  Found next game: {next_game['home']} vs {next_game['away']} at {next_game['game_start']}")
            
            before_price, after_price = get_prices_around_time(
                paper_log, next_game['game_id'], injury_time
            )
            
            if not before_price and not after_price:
                print(f"  No price data found for this game around the injury time.")
                continue
            
            result = {
                'player': player,
                'team': team,
                'injury_time': injury_time,
                'game_id': next_game['game_id'],
                'game_start': next_game['game_start'],
                'home_team': next_game['home'],
                'away_team': next_game['away'],
                'before_price': None,
                'after_price': None,
                'price_change': None,
                'time_before': None,
                'time_after': None
            }
            
            if before_price:
                result['before_price'] = float(before_price['p_home'])
                result['time_before'] = (parse_utc_timestamp(before_price['paper_utc']) - injury_time).total_seconds() / 3600
                print(f"  Price before injury: ${result['before_price']:.2f} ({result['time_before']:.1f} hours before)")
            
            if after_price:
                result['after_price'] = float(after_price['p_home'])
                result['time_after'] = (parse_utc_timestamp(after_price['paper_utc']) - injury_time).total_seconds() / 3600
                print(f"  Price after injury: ${result['after_price']:.2f} ({result['time_after']:.1f} hours after)")
            
            if result['before_price'] is not None and result['after_price'] is not None:
                result['price_change'] = result['after_price'] - result['before_price']
                print(f"  Price change: ${result['price_change']:.2f} ({'increase' if result['price_change'] > 0 else 'decrease'})")
            
            results.append(result)
            
        except Exception as e:
            print(f"  Error processing injury: {e}")
            continue
    
    if not results:
        print("\nNo complete injury lag analysis results found.")
        return
    
    print("\n=== SUMMARY ===")
    print(f"Successfully analyzed {len(results)} injuries with complete data.")
    
    # Calculate summary statistics
    price_changes = [r['price_change'] for r in results if r['price_change'] is not None]
    
    if price_changes:
        avg_change = sum(price_changes) / len(price_changes)
        print(f"\nAverage price change: ${avg_change:.2f} ({'increase' if avg_change > 0 else 'decrease'})")
        
        # Count how many times price moved in each direction
        increases = sum(1 for change in price_changes if change > 0)
        decreases = sum(1 for change in price_changes if change < 0)
        no_change = len(price_changes) - increases - decreases
        
        print(f"Price increases: {increases}/{len(price_changes)}")
        print(f"Price decreases: {decreases}/{len(price_changes)}")
        print(f"No price change: {no_change}/{len(price_changes)}")
    
    # Time lags
    time_befores = [r['time_before'] for r in results if r['time_before'] is not None]
    time_afters = [r['time_after'] for r in results if r['time_after'] is not None]
    
    if time_befores:
        avg_before = sum(time_befores) / len(time_befores)
        print(f"\nAverage time before injury: {avg_before:.1f} hours")
    
    if time_afters:
        avg_after = sum(time_afters) / len(time_afters)
        print(f"Average time after injury: {avg_after:.1f} hours")
    
    # Save detailed results
    with open('estudos/injury_lag_results.csv', 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'player', 'team', 'injury_time', 'game_id', 'game_start',
            'home_team', 'away_team', 'before_price', 'after_price',
            'price_change', 'time_before', 'time_after'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\nDetailed results saved to estudos/injury_lag_results.csv")

if __name__ == '__main__':
    main()
