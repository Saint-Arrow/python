import os
import re
import sys
from typing import List, Tuple

def parse_data_file(filename: str) -> List[Tuple[float, int]]:
    """
    Parse the input text file containing logic analyzer data.
    
    Args:
        filename: Path to the input file
    
    Returns:
        List of tuples (time, value) representing the parsed data
    """
    data = []
    raw_lines = []  # Store raw lines for output purposes
    
    with open(filename, 'r') as file:
        lines = file.readlines()
        
        # Skip the first line as it's not valid data
        for i in range(1, len(lines)):
            line = lines[i].strip()
            raw_lines.append(lines[i].strip())  # Store the raw line content
            if line:
                try:
                    parts = re.split(r'[,\s]+', line)
                    if len(parts) >= 2:
                        time = float(parts[0])
                        value = int(parts[1])
                        data.append((time, value))
                except ValueError:
                    # Skip lines that cannot be parsed
                    continue
                    
    return data, raw_lines


def find_high_pulse_durations_with_content(data: List[Tuple[float, int]], 
                                          raw_lines: List[str],
                                          min_duration: float, 
                                          max_duration: float) -> List[Tuple[float, int, str]]:
    """
    Find high-level pulse durations within the specified range.
    
    Args:
        data: List of (time, value) tuples
        raw_lines: List of raw line strings from the file
        min_duration: Minimum duration threshold in seconds
        max_duration: Maximum duration threshold in seconds
    
    Returns:
        List of tuples (duration, line_number, line_content) where duration is within the specified range
    """
    results = []
    
    for i in range(len(data) - 1):
        current_time, current_value = data[i]
        next_time, next_value = data[i + 1]
        
        # Check if we have a transition from high (1) to low (0)
        if current_value == 1 and next_value == 0:
            duration = next_time - current_time
            
            # Check if duration is within the specified range
            if min_duration <= duration <= max_duration:
                # Line number corresponds to the original file (starting from line 2 since line 1 is skipped)
                line_number = i + 2  # +2 because we skip line 1 and list indices start at 0
                
                # Get the corresponding raw line content
                # Adjust index to account for skipped first line
                line_content = raw_lines[i] if i < len(raw_lines) else ""
                
                results.append((duration, line_number, line_content))
                
    return results


def find_first_txt_file() -> str:
    """
    Find the first .txt file in the current directory.
    
    Returns:
        Path to the first .txt file found, or None if no .txt files exist
    """
    for filename in os.listdir('.'):
        if filename.lower().endswith('.txt'):
            return filename
    return None


def parse_arguments(args: List[str]) -> Tuple[float, float]:
    """
    Parse command line arguments for min and max duration.
    
    Args:
        args: Command line arguments list (excluding script name)
        
    Returns:
        Tuple of (min_duration, max_duration) in seconds
    """
    # Default values
    min_duration = 0.0005  # 500 microseconds in seconds
    max_duration = 0.001   # 1 millisecond in seconds
    
    # sys.argv includes script name as first argument, so actual args start from index 1
    if len(args) >= 1:
        try:
            min_duration = float(args[0])
            print(f"Setting minimum duration to: {min_duration}s ({min_duration*1e6}μs)")
        except ValueError:
            print(f"Warning: Invalid minimum duration '{args[0]}', using default {min_duration}")
    
    if len(args) >= 2:
        try:
            max_duration = float(args[1])
            print(f"Setting maximum duration to: {max_duration}s ({max_duration*1e6}μs)")
        except ValueError:
            print(f"Warning: Invalid maximum duration '{args[1]}', using default {max_duration}")
    
    return min_duration, max_duration


def main():
    """
    Main function to process the first .txt file in the current directory.
    """
    # Parse command line arguments (skip script name at index 0)
    min_duration, max_duration = parse_arguments(sys.argv[1:])
    
    # Find the first txt file in the current directory
    input_file = find_first_txt_file()
    
    if input_file is None:
        print("No .txt file found in the current directory.")
        return
        
    print(f"Processing file: {input_file}")
    
    try:
        data, raw_lines = parse_data_file(input_file)
        print(f"Parsed {len(data)} data points")
        
        print(f"Finding high-level pulses between {min_duration*1e6}μs and {max_duration*1e6}μs")
        results = find_high_pulse_durations_with_content(data, raw_lines, min_duration, max_duration)
        
        print(f"\nFound {len(results)} matching pulses:")
        print("Duration(s)\tLine Number\tDuration(μs)\tLine Content")
        
        for duration, line_num, line_content in results:
            print(f"{duration:.8f}\t\t{line_num}\t\t{duration*1e6:.2f}\t\t{line_content}")
            
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    main()