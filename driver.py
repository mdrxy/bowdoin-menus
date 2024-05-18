import os
from dotenv import load_dotenv
import requests
import datetime
import xml.etree.ElementTree as ET
import json
import re

load_dotenv()

botID = os.getenv('BOT_ID')
menuAPI = "https://apps.bowdoin.edu/orestes/api.jsp"
groupmeAPI = "https://api.groupme.com/v3/bots/post"

class Location():
    MOULTON = 48
    THORNE = 49

class Meals():
    BREAKFAST = "breakfast"
    BRUNCH = "brunch"
    LUNCH = "lunch"
    DINNER = "dinner"
    
    def getUpcomingMeal(location):
        """
        The next upcoming meal is set after the current meal expires.
        
        During a meal period, it is still "upcoming".
        
        Only handles full hours, so 12:30 p.m. is rounded up to 1 p.m.
        """

        currentHour = datetime.datetime.now().time().hour
        currentDay = datetime.datetime.now().strftime("%a").lower()
        
        if location == Location.MOULTON:
            # Monday–Friday
            if currentDay != "sat" and currentDay != "sun":
                # Breakfast: 7:00 a.m. to 10:00 a.m.
                if 0 <= currentHour < 10 or 19 <= currentHour < 24:
                    if (currentDay == "fri" and 19 <= currentHour < 24):
                        return Meals.BRUNCH
                    else:
                        return Meals.BREAKFAST
                # Lunch: 11:00 a.m. to 2:00 p.m.
                if 10 <= currentHour < 14:
                    return Meals.LUNCH
                # Dinner: 5:00 p.m. to 7:00 p.m.
                if 14 <= currentHour < 19:
                    return Meals.DINNER

            # Saturday–Sunday
            if currentDay == "sat" or currentDay == "sun":
                # Breakfast: 8:00 a.m. to 11:00 a.m.            
                if 0 <= currentHour < 11 or 19 <= currentHour < 24:
                    if currentDay == "sun" and 19 <= currentHour < 24:
                        return Meals.BREAKFAST
                    return Meals.BRUNCH
                # Brunch: 11:00 a.m. to 12:30 p.m.
                if 11 <= currentHour < 13:
                    return Meals.LUNCH
                # Dinner: 5:00 p.m. to 7:00 p.m.    
                if 13 <= currentHour < 19:
                    return Meals.DINNER
            
        if location == Location.THORNE:
            # Monday–Friday
            if currentDay != "sat" and currentDay != "sun":
                # print("Weekday")
                # Breakfast: 8:00 a.m. to 10:00 a.m.
                if 0 <= currentHour < 10 or 20 <= currentHour < 24:
                    if (currentDay == "fri" and 20 <= currentHour < 24):
                        # print("Brunch")
                        return Meals.BRUNCH
                    else:
                        print("Breakfast")
                        return Meals.BREAKFAST
                # Lunch: 11:30 a.m. to 2:00 p.m.
                if 10 <= currentHour < 14:
                    # print("Lunch")
                    return Meals.LUNCH
                # Dinner: 5:00 p.m. to 8:00 p.m.
                if 14 <= currentHour < 20:
                    # print("Dinner")
                    return Meals.DINNER

            # Saturday–Sunday
            if currentDay == "sat" or currentDay == "sun":
                # print("Sat or Sun")
                
                # Brunch: 11:00 a.m. to 1:30 p.m.
                if 0 <= currentHour < 14 or 20 <= currentHour < 24:
                    if currentDay == "sun" and 20 <= currentHour < 24:
                        return Meals.BREAKFAST
                    return Meals.BRUNCH
                # Dinner:  5:00 p.m. to 7:30 p.m.
                if 14 <= currentHour < 20:
                    return Meals.DINNER
    
def buildRequest(location):
    currentDate = datetime.datetime.now().strftime("%Y%m%d")
    locationUnit = location
    
    requestData = {
        'unit': {locationUnit},
        'date': {currentDate},
        'meal': {Meals.getUpcomingMeal(location)}
    }
    
    return requestData

def request(location):
    response = requests.post(menuAPI, data=buildRequest(location))
    
    if response.status_code == 200:
        return response.content
    else:
        print("Error:", response.status_code)
    
def parseResponse(requestContent):
    root = ET.fromstring(requestContent)
    
    courseValues = []
    itemNames = []

    # Iterate over each 'record' element in the XML
    for record in root.findall('.//record'):
        # Extract 'course' and 'formal_name' values from each 'record' element
        course = record.find('course').text
        webLongName = record.find('webLongName').text
        
        # Append the values to the respective lists
        courseValues.append(course)
        itemNames.append(webLongName)
    
    menu = {key: [] for key in set(courseValues)}
    
    i = 0
    for item in itemNames:
        if item: # Sometimes a NoneType item would be returned
            # Remove consecutive spaces from Strings
            item = re.sub(r'\s+', ' ', item)
        menu[courseValues[i]].append(item)
        i += 1
        
    custom_order = ['Main Course', 'Desserts']
    sorted_menu = {key: menu[key] for key in custom_order if key in menu}
    sorted_menu.update({key: menu[key] for key in menu if key not in sorted_menu})    
    
    return sorted_menu

def stringify(location, menu):
    meal = Meals.getUpcomingMeal(location)
    
    outputString = ""
    if location is Location.MOULTON:    
        outputString += f"Moulton Union {meal.capitalize()}:"
    if location is Location.THORNE:    
        outputString += f"Thorne {meal.capitalize()}:"
    outputString += '\n\n'

    for category, items in menu.items():
        outputString += f"{category}:\n"
        for item in items:
            outputString += f"- {item}\n"
        outputString += "\n"
        
    return outputString

def sendMessage(text):
    jail_date = datetime.datetime(year=2023, month=3, day=29)
    current_date = datetime.datetime.now()
    days_difference = (current_date - jail_date).days
    
    evan = ""
    evan += text
    evan += f"Evan Gershkovich:\n- {days_difference} days"
    
    data = {
        'text': evan,
        'bot_id': botID
    }
    
    headers = {'Content-Type': 'application/json'}
    
    response = requests.post(groupmeAPI, data=json.dumps(data), headers=headers)

    if response.status_code == 200 or \
        response.status_code == 201 or \
            response.status_code == 202:
        print("Message posted successfully.")
    else:
        print("Error:", response.status_code)

if __name__ == "__main__":
    thorne = request(Location.THORNE)
    thorneMenu = parseResponse(thorne)
    
    moulton = request(Location.MOULTON)
    moultonMenu = parseResponse(moulton)

    thorneText = stringify(Location.THORNE, thorneMenu)
    if len(thorneText) < 1000:
        sendMessage(thorneText)    
    
    moultonText = stringify(Location.MOULTON, moultonMenu)
    if len(moultonText) < 1000:
        sendMessage(moultonText)