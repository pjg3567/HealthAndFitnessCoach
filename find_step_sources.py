#
# Description:
# This is a utility script to help identify the 'sourceName' attributes for
# step count records in the large 'export.xml' file without having to open it manually.
#
# It scans the XML and prints a list of all unique source names found for step counts.
# The output can then be used to correctly configure the ALLOWED_STEP_SOURCES
# list in the main 'create_daily_summary.py' script.
#

import xml.etree.ElementTree as ET
import os

def find_unique_step_sources():
    """
    Scans the Apple Health XML to find and print all unique sources
    that have contributed step count data.
    """
    file_path = os.path.join('data_exports', 'apple_health_export', 'export.xml')
    
    if not os.path.exists(file_path):
        print(f"ERROR: The file was not found at '{file_path}'.")
        return

    print(f"Scanning '{file_path}' for step count sources. This might take a moment...")

    try:
        context = ET.iterparse(file_path, events=('start', 'end'))
        
        # A 'set' is used to automatically store only unique items.
        unique_sources = set()

        for event, elem in context:
            if event == 'end' and elem.tag == 'Record':
                # Check if the record is a step count record
                if elem.get('type') == 'HKQuantityTypeIdentifierStepCount':
                    source = elem.get('sourceName')
                    if source:
                        unique_sources.add(source)
                
                # We must still clear the element to keep memory usage low
                elem.clear()

        print("\n--- Unique Step Count Sources Found ---")
        if unique_sources:
            for source in sorted(list(unique_sources)): # Sort the list for clean display
                print(f"- {source}")
        else:
            print("No sources for step counts were found.")
        print("\n" + "-" * 40)
        print("Copy the relevant device name(s) from this list into the")
        print("'ALLOWED_STEP_SOURCES' list in the 'create_daily_summary.py' script.")


    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    find_unique_step_sources()