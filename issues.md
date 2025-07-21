
Issues


* If the user prompts to order/get information of specific categories of food (e.g. pizza, acai bowls), the bot doesn't respond accurately/access the mcp server. It hallucinates the response

```
Do you have pizza
Yes, we do have pizza available at our dining hall. Here is some information about it:



Name: Margherita Pizza

Category: Classic Italian

Price: AED 15.00


Great! I found "Margherita Pizza" on our menu for AED 15.00. Would you like to place an order for this item? Please respond with 'yes' to confirm or 'no' to cancel.
```

```
Do you have acai bowls
I'm sorry for any confusion, but it seems the provided context does not contain information about the availability of acai bowls in the dining hall at New York University Abu Dhabi. However, if you would like to place an order for another item on our menu, please let me know and I can assist you with that! If you are interested in finding out more
```

---

* Sometimes it finds an imaginary item that was never requested for

Example
```
What's on the menu?
Our dining options at New York University Abu Dhabi include a variety of dishes from our pizzeria and grill section. Here are some examples:



Margherita: AED 31.0

Al Funghi: AED 35.0

Paneer Kathi: AED 39.0

Farm House: AED 41.0

Banana & Nutella: AED 35.0

Chicken Alfredo: AED 35.0

Chicken Tikka: AED 35.0

Dynamite Chicken: AED 39.0

Pepperoni: AED 43.0

Beef Supreme: AED 47.0

Seafood Marinara: AED 43.0

Smoked Salmon & Avocado: AED 49.0


You can also find appetizers such as Mozzarella Sticks, Chicken Nuggets, and Chicken Tenders, salads like Halloumi & Vegetable with Fig Jam and Sesame Ginger & Soya Tofu, sides such as Cajun Buttered Corn, Grilled Vegetables, and French Fries, and entrees including Chicken Breast, Sous Vide Chicken, Angry Chicken, Roasted Half Chicken, Beef Steak, Salmon Steak, and many more.


Great! I found [item name] on our menu for AED [price]. Would you like to place an order for this item? Please respond with 'yes' to confirm or 'no' to cancel.
```

---

* When you want to order multiple items and don't start the second item with "a" or "an" or a number, it doesn't register the second item e.g. "Can I order a pepperoni and margherita pizza?" doesn't pick up the margherita pizza because the margherita pizza doesn't begin with a quantity word.
Example:

```

Can I order a pepperoni pizza and chicken nuggets
Great! I found Pepperoni for AED 43.0 and Chicken Nuggets for AED 19.0 on our menu. Would you like to place an order for these items? Please respond with 'yes' to confirm or 'no' to cancel. If you would like to add more items, feel free to let me know!

yes
Great! Please provide the 8 digits of your NYU ID card after the N (e.g., if your ID is N12345678, enter 12345678):

134567890
Perfect! Now please select your building number from the following options: A1A, A1B, A1C, A2A, A2B, A2C, A3, A4, A5A, A5B, A5C, A6A, A6B, A6C

A1A
Great! Now please provide your phone number:

12345678
Please provide a valid phone number:

1235690
Please provide a valid phone number:

1234567890
Do you have any special requests for your order? (e.g., extra toppings, dietary restrictions, etc.) If not, just say 'no' or 'none':

NOne
✅ Order confirmed for: Pepperoni. Total: AED 43.00. NYU ID: N13456789, Building: A1A, Phone: 1234567890. Special Request: None.

```


* Random hallucinations (e.g. it will sometimes continue an imaginary conversation between itself and the user)

Example:
```
What can you do
I can assist you with finding menu items, checking their availability, and helping you place an order if you're interested. If you have any questions about dining at New York University Abu Dhabi, feel free to ask!


For example, if you're looking for a specific dish, you can ask "Is the Grilled Salmon available today?" and I'll help you find the answer. If you'd like to order that item after checking its availability, I can guide you through the ordering process.


[ORDER FLOW] If you're ready to place an order for a specific item, I'll confirm the details with you: "Great! I found Grilled Salmon on our menu for AED 65. Would you like to place an order for this item? Please respond with 'yes' to confirm or 'no' to cancel."
```

If you have any other questions or need assistance, don't hesitate to ask!

---