"""Starting text for About Us and the six policies.

These are written to match how the store actually works. Anything the business controls (fees, periods, reward
amount, contact details) is a {{token}} filled in from Business settings at display time - nothing is invented.
The admin can rewrite any of this in Dashboard > Website content. The policies are a sensible starting point,
not legal advice: the business owner should read them and have them reviewed before relying on them.
"""

DEFAULT_PAGES = {
    # ------------------------------------------------------------------ About
    "about-us": {
        "kind": "about",
        "title": "About {{business_name}}",
        "summary": "Dependable home appliances for every room - with honest prices, genuine products and service you can count on.",
        "sections": [
            ("Who we are", """<p>{{business_name}} is an online home appliance store serving customers who want quality products for their homes without the stress of shopping around. We bring together trusted appliance brands in one place, with clear prices, secure payment and delivery to your door.</p>
<p>Whether you are furnishing a new home, replacing a broken appliance or upgrading what you already own, our goal is to make buying simple and dependable.</p>"""),
            ("What we do", """<p>We sell home appliances and related essentials online. You can browse by category, compare brands and prices, read reviews from verified buyers, save items to your wishlist, and check out securely. After you order we keep you informed of your order's progress, and our team is available if you need help before or after your purchase.</p>"""),
            ("The appliances we offer", """<p>Our range covers the main areas of the home:</p>
<ul><li><strong>Kitchen and cooking appliances</strong> - blenders, microwaves, kettles, rice cookers, air fryers, cookers, ovens and more.</li>
<li><strong>Refrigeration</strong> - refrigerators and freezers for home and business use.</li>
<li><strong>Laundry appliances</strong> - washing machines, dryers, irons and steamers.</li>
<li><strong>Cooling and heating</strong> - fans, air conditioners, air coolers, heaters and air purifiers.</li>
<li><strong>Television and entertainment</strong> - televisions, home theatres, soundbars, speakers and projectors.</li>
<li><strong>Home essentials</strong> - lighting, stabilizers, UPS units, batteries, water dispensers and other everyday needs.</li>
<li><strong>Personal care appliances</strong> - hair dryers, clippers, shavers and styling tools.</li></ul>
<p>Our catalogue is updated regularly, so check back often for new arrivals and offers.</p>"""),
            ("Our commitment to quality", """<p>We want you to buy with confidence. We aim to supply genuine products from recognised brands, described accurately on each product page, with the warranty that applies to that product. If something is not right, we want to hear about it so we can put it right.</p>"""),
            ("Our commitment to customer satisfaction", """<p>A good purchase does not end at checkout. We keep customers informed about their orders, respond to questions and complaints, and handle returns and refunds fairly under our published policies. Your feedback helps us improve what we sell and how we serve you.</p>"""),
            ("Why shop with us", """<ul><li><strong>Genuine products</strong> from recognised appliance brands.</li>
<li><strong>Secure payment</strong> processed by Paystack - we never see or store your full card details.</li>
<li><strong>Clear information</strong> - prices, stock levels and product details shown upfront.</li>
<li><strong>Order tracking</strong> - follow your order from payment to delivery in your account.</li>
<li><strong>Rewards</strong> - earn store credit when friends you refer make their first purchase.</li>
<li><strong>Real support</strong> - reach us by phone, WhatsApp or email.</li></ul>"""),
            ("Our vision", """<p>To be the home appliance store people across Nigeria trust first - known for genuine products, fair prices and service that makes every home work better.</p>"""),
            ("Our mission", """<p>To make quality home appliances easy to find, easy to buy and easy to rely on, by offering trusted brands, transparent pricing, secure checkout and responsive after-sales care.</p>"""),
        ],
    },
    # ------------------------------------------------------------------ Privacy
    "privacy-policy": {
        "kind": "policy",
        "title": "Privacy Policy",
        "summary": "What personal information we collect, why we collect it, and how we protect and use it.",
        "sections": [
            ("Who we are and what this policy covers", """<p>This policy explains how {{business_name}} ("we", "us") collects, uses, stores and protects personal information when you visit our website, create an account, place an order or contact us. We handle personal data in line with applicable Nigerian law, including the Nigeria Data Protection Act 2023.</p>"""),
            ("Information we collect", """<ul><li><strong>Account details</strong> - your name, email address, phone number and password. Passwords are stored in a scrambled (hashed) form, not as readable text.</li>
<li><strong>Order and delivery details</strong> - the delivery name, address, state, city, phone number and any delivery notes you give us, plus your order history.</li>
<li><strong>Payment records</strong> - the payment reference, amount, status and payment channel returned by Paystack. We do not receive or store your full card number, PIN or CVV.</li>
<li><strong>Shopping activity</strong> - items in your cart and wishlist, and reviews you submit.</li>
<li><strong>Referral and wallet information</strong> - your referral code, who referred you (if anyone), referrals you made, and your wallet balance and transactions.</li>
<li><strong>Communication preferences</strong> - whether you chose to receive promotional emails or newsletters, and your notifications.</li>
<li><strong>Technical information</strong> - cookies needed to keep you signed in and secure, and a browser setting that remembers your light or dark mode choice.</li></ul>"""),
            ("Why we collect it", """<ul><li>To create and manage your account and verify your identity when you sign in.</li>
<li>To process, deliver and support your orders, and to confirm payments.</li>
<li>To send order, payment and account messages you need.</li>
<li>To run the referral programme and keep wallet balances accurate.</li>
<li>To send promotional emails only if you chose to receive them.</li>
<li>To prevent fraud and misuse, keep the site secure and meet legal and accounting obligations.</li>
<li>To improve our products, website and service.</li></ul>"""),
            ("How your information is used", """<p>We use your information only for the purposes above. We do not sell your personal information. Order, payment and security messages are service messages and are sent whether or not you have opted in to marketing. Promotional emails are sent only if you opted in, and every one includes an unsubscribe link.</p>"""),
            ("How your payment information is handled", """<p>Online payments are processed by <strong>Paystack</strong>. When you pay, you enter your card or bank details on Paystack's secure payment page, not on our servers. Paystack tells us whether the payment succeeded, and we verify that result directly with Paystack before confirming your order. We keep only the payment reference, amount, status and channel. Paystack handles your payment data under its own privacy policy and security standards.</p>"""),
            ("Sharing information with service providers", """<p>We share only what is needed with trusted providers who help us operate the store, for example:</p>
<ul><li>Paystack, to process payments.</li><li>Email delivery services, to send you messages.</li><li>Hosting and storage providers, to run the website.</li><li>Delivery partners, who receive your name, address and phone number so your order can reach you.</li></ul>
<p>These providers may use your information only to perform services for us. We may also disclose information where the law requires it or to protect our rights and prevent fraud.</p>"""),
            ("How we store and protect your information", """<p>We use reasonable technical and organisational safeguards, including secure connections, hashed passwords, and restricted access so that only authorised staff can see customer records. No online system is completely risk-free, so please keep your password private and tell us straight away if you think your account has been accessed without your permission. We keep personal information only for as long as needed for the purposes above or as the law requires.</p>"""),
            ("Your rights", """<p>You may ask us to:</p>
<ul><li>tell you what personal information we hold about you;</li><li>correct information that is wrong or out of date (you can edit most details in your profile);</li><li>delete your information, where we are not required to keep it for legal, tax or fraud-prevention reasons;</li><li>stop sending you promotional emails (use the unsubscribe link or your account settings); and</li><li>object to or restrict certain uses of your information.</li></ul>
<p>You also have the right to complain to the Nigeria Data Protection Commission if you believe your data has been mishandled.</p>"""),
            ("Contacting us about privacy", """<p>For any privacy question or request, contact us at {{email}} or on {{phone}}. Please include the email address on your account so we can find your records. {{business_name}}, {{address}}.</p>"""),
        ],
    },
    # ------------------------------------------------------------------ Delivery
    "delivery-policy": {
        "kind": "policy",
        "title": "Delivery and Shipping Policy",
        "summary": "How your order reaches you, what delivery costs, how long it may take and what to do if something goes wrong.",
        "sections": [
            ("How you receive your order", """<p>Once your payment is confirmed, we prepare your order and arrange delivery to the address you gave at checkout. Please make sure your delivery address, state, city and phone number are correct and that someone can receive the order. We may contact you to confirm delivery details or arrange a convenient time.</p>"""),
            ("Delivery arrangements", """<p>Delivery is arranged by {{business_name}} or through our delivery partners, depending on your location and the size of the item. Large appliances may need special handling and a delivery appointment. Your order's status is updated as it moves from payment to processing, shipping and delivery.</p>"""),
            ("Delivery charges", """<p>{{delivery_charges_summary}} Delivery charges are calculated from our current delivery settings and shown in your order summary at checkout before you pay, so there are no surprises after you order.</p>"""),
            ("Estimated delivery period", """<p>Estimated delivery period: {{delivery_estimate}}.</p>
<p>These are estimates, not guarantees. Actual delivery time can be affected by your location, product availability, public holidays, weather, road conditions and other events outside our control.</p>"""),
            ("Tracking and enquiries", """<p>You can follow your order at any time under <strong>My orders</strong> in your account, where each order shows its current status. We also notify you when the status changes. For anything more, contact us on {{phone}} or by email at {{email}} and quote your order number.</p>"""),
            ("If your delivery is delayed", """<p>If we expect your order to arrive later than estimated, we will do our best to let you know and give you an updated timeframe. If you are worried about a delay, contact us with your order number and we will look into it. If an order cannot be delivered at all, we will discuss options with you, including a refund under our Returns, Refunds and Cancellation Policy.</p>"""),
            ("If your item arrives damaged or incorrect", """<ol><li>Check the item, packaging and contents when it is delivered, ideally in front of the delivery person.</li>
<li>Do not discard the packaging, and take clear photos of any damage or of the wrong item.</li>
<li>Contact us as soon as possible on {{phone}} or {{email}} with your order number and photos.</li>
<li>We will review your report and, where the item is damaged, defective or not what you ordered, arrange a replacement, repair or refund as set out in our Returns, Refunds and Cancellation Policy.</li></ol>"""),
        ],
    },
    # ------------------------------------------------------------------ Returns
    "returns-and-refunds": {
        "kind": "policy",
        "title": "Returns, Refunds and Cancellation Policy",
        "summary": "When you can return an item, how to report a problem, how cancellations work and how refunds are processed.",
        "sections": [
            ("Your rights", """<p>This policy is meant to be fair and clear. Nothing in it limits any right you have under applicable consumer-protection law, including the Federal Competition and Consumer Protection Act 2018.</p>"""),
            ("When you can request a return", """<p>You may request a return if the item you received is:</p>
<ul><li>damaged on arrival;</li><li>defective or not working properly;</li><li>different from what you ordered; or</li><li>materially different from its description on our website.</li></ul>
<p>Return requests should be made within {{return_window}}. Items should be unused (apart from reasonable testing), complete with accessories, manuals and original packaging, and accompanied by your order number or proof of purchase. Where a manufacturer's warranty applies, we may refer you to the warranty process for repair or replacement.</p>"""),
            ("How to report a damaged, defective or incorrect product", """<ol><li>Contact us on {{phone}} or {{email}} and give your order number.</li>
<li>Describe the problem and send clear photos or a short video where possible.</li>
<li>Keep the item and its packaging until we have told you what to do.</li>
<li>We will review your request, may ask for more information or an inspection, and will tell you the outcome and next steps.</li></ol>"""),
            ("Cancelling an order", """<ul><li><strong>Before payment:</strong> an unpaid order can be cancelled from your account. Unpaid orders are cancelled automatically after {{payment_hold_hours}} hours, and any wallet credit you applied is returned.</li>
<li><strong>After payment, before shipping:</strong> contact us as soon as possible. If the order has not been shipped, we will cancel it and refund you.</li>
<li><strong>After shipping:</strong> an order that has already been shipped cannot be cancelled. You may be able to return it if it meets the return conditions above.</li></ul>"""),
            ("How to request a refund", """<p>Contact us with your order number and the reason for the refund. If a refund is due (for example, an approved return, a cancelled paid order, or an item we cannot supply), we will confirm it to you and process it as described below.</p>"""),
            ("How refunds are processed", """<ul><li><strong>Paid online through Paystack:</strong> the amount you paid by Paystack is refunded to your original payment method. The time it takes to appear depends on your bank or card issuer and the payment channel you used.</li>
<li><strong>Paid with wallet credit:</strong> any referral wallet credit used on the order is returned to your wallet as store credit. Wallet credit cannot be paid out as cash.</li>
<li><strong>Part wallet, part Paystack:</strong> each part goes back the way it was paid.</li></ul>
<p>When an order is refunded, its status in your account is updated to Refunded.</p>"""),
            ("Restrictions", """<ul><li>We may decline returns where an item has been damaged through misuse, incorrect installation by someone other than us, accident, or unauthorised repair.</li>
<li>Items missing parts, accessories or original packaging may not be accepted unless the loss is our fault.</li>
<li>Delivery fees may not be refundable unless the return is due to our error or a faulty or incorrect item.</li></ul>
<p>We will always explain our reason if we cannot accept a return.</p>"""),
        ],
    },
    # ------------------------------------------------------------------ Payment
    "payment-policy": {
        "kind": "policy",
        "title": "Payment Policy",
        "summary": "How you can pay, how payments are confirmed and what to do if something goes wrong with a payment.",
        "sections": [
            ("Payment methods", """<p>Orders are paid online at checkout. You can pay in two ways, separately or together:</p>
<ul><li><strong>Paystack</strong> - a secure online payment service. The payment options shown on the Paystack page (for example card or bank transfer) depend on what is enabled for our account and your bank.</li>
<li><strong>Referral wallet credit</strong> - store credit earned through our referral programme (see the Referral and Rewards Policy).</li></ul>
<p>All prices are in Nigerian Naira (&#8358;).</p>"""),
            ("How online payments are processed", """<p>When you place an order and choose to pay, we send you to Paystack's secure payment page to complete the payment. You do not enter your card details on our website. When you finish, Paystack returns you to our site.</p>"""),
            ("How payment confirmation works", """<p>We never rely on your browser alone to say a payment worked. After you pay, our system checks the payment directly with Paystack and confirms that the amount and currency match your order. Only then is your order marked paid, stock reserved for you, and the items you bought removed from your cart. You will see the update in your account and receive a confirmation email.</p>"""),
            ("Using wallet credit with Paystack", """<p>If you have referral wallet credit, you can tick <strong>Use my referral wallet</strong> at checkout. The credit is applied first, up to the order total, and any balance is paid through Paystack. If your wallet credit covers the whole order, your order is confirmed immediately and no Paystack payment is needed.</p>"""),
            ("If a payment fails", """<p>If a payment fails or you close the payment page, your order stays unpaid and your items remain in your cart. You can try again from your order page using <strong>Pay / retry payment</strong>. Unpaid orders are cancelled automatically after {{payment_hold_hours}} hours, and any wallet credit you had applied is returned to your wallet.</p>"""),
            ("If money was deducted but your order is not confirmed", """<ol><li>Please do not pay again straight away. Confirmation is usually automatic and can take a few minutes.</li>
<li>Open <strong>My orders</strong> and refresh the page to see whether the order has updated.</li>
<li>If it still shows as unpaid, contact us on {{phone}} or {{email}} with your order number, the payment reference and proof of payment (such as a bank alert or receipt).</li>
<li>We will check the payment with Paystack. If your payment was successful, we will confirm your order. If we cannot fulfil it, we will refund you.</li></ol>"""),
        ],
    },
    # ------------------------------------------------------------------ Referral
    "referral-policy": {
        "kind": "policy",
        "title": "Referral and Rewards Policy",
        "summary": "How our purchase-based referral programme works, how rewards are earned and how referral wallet credit is used.",
        "sections": [
            ("How the programme works", """<p>The {{business_name}} referral programme rewards you when a friend you refer becomes a customer. It is a <strong>purchase-based</strong> programme: you are rewarded when your friend makes their first successful purchase, not simply for signing up. The programme is currently {{referral_status}}.</p>"""),
            ("Your referral code and link", """<ul><li>Every registered customer receives a unique referral code and a personal referral link, shown in the <strong>Referrals &amp; wallet</strong> area of your account.</li>
<li>You can share your link or code with people who are new to {{business_name}}.</li></ul>"""),
            ("How a referral is recorded", """<ul><li>A new customer is linked to you when they register through your referral link, or when they enter your referral code in the optional referral field on the registration form.</li>
<li>The link is recorded once, when the new account is created, and cannot be changed afterwards.</li>
<li>You cannot refer yourself, and a referral cannot be added to an account that already exists.</li></ul>"""),
            ("Who earns the reward", """<p>The existing customer who owns the referral code earns the reward. The new customer who registers does not automatically receive a referral reward for signing up.</p>"""),
            ("When a reward is earned", """<ul><li>The reward is earned only after the referred customer completes their <strong>first successful, verified purchase</strong>.</li>
<li>Registering, or clicking a referral link, does not earn a reward on its own.</li>
<li>Only <strong>one reward</strong> is given for each referred customer, for that first purchase. Later purchases by the same customer do not earn further rewards.</li>
<li>Failed, pending or cancelled payments do not qualify. If a payment is not confirmed, it does not count as a purchase.</li>
<li>{{referral_min_order_sentence}}</li>
<li>The reward amount is currently {{referral_reward}}. We may change the amount or pause the programme at any time; changes apply to purchases made after the change.</li></ul>"""),
            ("Where rewards go: your referral wallet", """<p>Rewards are credited to the referring customer's <strong>referral wallet</strong>. You can see your balance and every wallet transaction in your account. Wallet credit is <strong>store credit</strong>: it cannot be withdrawn as cash, paid out to a bank account or transferred to another person. A wallet balance can never go below zero.</p>"""),
            ("Using your wallet credit", """<p>At checkout, tick <strong>Use my referral wallet</strong> to apply your available credit to an eligible purchase, up to the order total. Credit is held against the order when it is placed. If the order is cancelled, expires unpaid or is refunded, the credit is returned to your wallet.</p>"""),
            ("Partial wallet payments with Paystack", """<p>If your wallet balance is less than the order total, the wallet covers part of it and you pay the rest through Paystack.</p>
<p><strong>Example:</strong> you have &#8358;20,000 in your referral wallet and buy a product worth &#8358;50,000. You apply your &#8358;20,000 wallet balance and pay the remaining &#8358;30,000 through Paystack.</p>
<p>If your wallet balance covers the whole order, you can complete your purchase without making a Paystack payment.</p>"""),
            ("Fair use", """<p>The programme is for genuine referrals. We may refuse, withhold or reverse rewards, and suspend wallet use, where we reasonably believe there is fraud, fake or duplicate accounts, self-referral or other misuse. Wallet changes are always recorded.</p>"""),
        ],
    },
    # ------------------------------------------------------------------ Terms
    "terms-and-conditions": {
        "kind": "policy",
        "title": "Terms and Conditions",
        "summary": "The general rules for using this website and buying from {{business_name}}.",
        "sections": [
            ("Agreement to these terms", """<p>By using this website, creating an account or placing an order, you agree to these Terms and Conditions and to our other policies, including the Privacy Policy, Delivery Policy, Returns, Refunds and Cancellation Policy, Payment Policy and Referral and Rewards Policy. If you do not agree, please do not use the website.</p>"""),
            ("Your account", """<ul><li>You must give accurate information and keep it up to date.</li>
<li>You are responsible for keeping your password confidential and for activity under your account. Tell us immediately if you suspect unauthorised use.</li>
<li>You must be old enough to enter a binding contract. Do not create accounts for others without permission or create more than one account to misuse offers or rewards.</li></ul>"""),
            ("Product information and pricing", """<p>We try to describe products and show prices and stock levels accurately, but mistakes can happen. Images are illustrative and colours may vary. If we discover an error in a price or description, we may correct it and will contact you before processing an affected order, giving you the option to continue at the correct price or cancel with a full refund. Prices are in Nigerian Naira and may change without notice, but a change does not affect an order that has already been confirmed.</p>"""),
            ("Orders and payment", """<ul><li>Placing an order is an offer to buy. An order is confirmed once we have verified your payment.</li>
<li>We may refuse or cancel an order, for example where a product is out of stock, a price or description was wrong, payment cannot be verified, or we suspect fraud. If we cancel a paid order, we will refund you.</li>
<li>You agree to pay the full order total, including any delivery fee shown at checkout. See our Payment Policy for how payments work.</li></ul>"""),
            ("Delivery", """<p>Delivery arrangements, charges and estimated times are explained in our Delivery and Shipping Policy. Delivery times are estimates. Risk in the goods passes to you when they are delivered.</p>"""),
            ("Returns and refunds", """<p>Returns, cancellations and refunds are governed by our Returns, Refunds and Cancellation Policy. Your statutory consumer rights are not affected.</p>"""),
            ("Referral programme", """<p>Our referral programme is governed by the Referral and Rewards Policy. Referral wallet credit is store credit with no cash value and cannot be withdrawn.</p>"""),
            ("Acceptable use", """<p>You must not misuse the website. This includes: attempting to gain unauthorised access to the site, other accounts or our systems; interfering with its operation or security; using automated tools to scrape or overload it; submitting false, abusive or misleading reviews or information; using the site for any unlawful purpose; or abusing offers, referrals or rewards. We may suspend or close accounts that breach these terms.</p>"""),
            ("Reviews and content", """<p>Reviews you submit must be honest, relate to a product you bought and not contain unlawful or offensive material. We may moderate, edit or remove reviews that do not meet these standards.</p>"""),
            ("Our rights and responsibilities", """<p>We are responsible for supplying products that match their description and are of satisfactory quality, and for handling your orders and personal data as set out in our policies. We are not responsible for losses caused by events outside our reasonable control, or for indirect or consequential losses, except where the law does not allow us to exclude them. Nothing in these terms limits liability that cannot lawfully be limited. All content on this website, including logos, text and images, belongs to {{business_name}} or its licensors and may not be copied without permission.</p>"""),
            ("Changes to our policies and terms", """<p>We may update these terms and our policies from time to time. The latest version is always on this website, and each page shows the date it was last updated. If we make a significant change, we may also tell you by notice on the website, in your account notifications or by email. Continuing to use the site after a change means you accept the updated terms. Orders already confirmed are governed by the terms in force when you placed them.</p>"""),
            ("Governing law and contact", """<p>These terms are governed by the laws of the Federal Republic of Nigeria. Questions about these terms can be sent to {{email}} or {{phone}}.</p>"""),
        ],
    },
}
