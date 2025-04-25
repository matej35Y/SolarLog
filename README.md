# Solar Earnings Tracker

Овој проект е изработен како практична апликација за следење на енергетска продукција од соларна централа и нејзината моментална и историска заработка.
Апликацијата ја собира продукцијата од хардвер(SolarLog Base-2000) поврзан на локален компјутер и ги комбинира податоците со пазарните цени на електрична енергија,
кои ги зимам преку web scraping, за да изврши пресметки на финансиска вредност.
Проектот е целосно напишан во Python и користи SQLite како база за складирање на податоците. Податоците се освежуваат преку API повици, симулирајќи ги настаните на refresh на страната. За пристап до локалниот компјутер од далечина е користена Tailscale, peer-to-peer VPN мрежа која овозможува безбеден и едноставен пристап без сложена мрежна конфигурација.
Frontend делот е изграден со HTML, Bootstrap и Chart.js, и овозможува визуелизација на:
дневна анализа на продукција по часови
месечна анализа со сумирани вредности по денови
вкупна вредност на енергијата во евра, базирана на реални пазарни цени
Ова решение опфаќа повеќе области: backend развој, интеграција со хардвер (IoT), web scraping, работа со бази на податоци и основи на мрежна комуникација преку VPN.



🛠️ Користени алатки и технологии

Python – главен јазик за логика, пресметки и API
FastAPI – за креирање на API ендпоинти
SQLite – лесна база за чување историски податоци
BeautifulSoup + Requests – за web scraping на цени на електрична енергија
HTML + Bootstrap – за frontend структура и дизајн
Chart.js – за прикажување на графици со продукција и вредности
Tailscale – за peer-to-peer поврзување со локалниот компјутер
Jinja2 – за темплејт рендерирање во HTML
Uvicorn – за покренување на FastAPI апликацијата


////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


This project is built as a practical application for tracking energy production from a solar power plant and calculating its real-time and historical earnings.
The application collects production data from hardware (SolarLog Base-2000) connected to a local computer,
and combines it with market electricity prices obtained via web scraping, to calculate the financial value of the generated energy.
The project is fully written in Python and uses SQLite as a database for storing data. The data is refreshed through API calls that are triggered by simulated page refresh events. To access the local computer remotely, Tailscale is used – a peer-to-peer VPN network that enables secure and easy connection without complex network configuration.
The frontend is built with HTML, Bootstrap, and Chart.js, providing visualization of:
daily production analysis by hour
monthly analysis with aggregated values per day
total energy value in EUR, based on real-time market prices
This solution touches on multiple domains: backend development, hardware (IoT) integration, web scraping, database management, and basic network communication over VPN.



🛠️ Tools and Technologies Used

Python – main language for logic, calculations, and API
FastAPI – for creating API endpoints
SQLite – lightweight database for storing historical data
BeautifulSoup + Requests – for scraping electricity price data
HTML + Bootstrap – for frontend structure and styling
Chart.js – for visualizing energy production and value data
Tailscale – for peer-to-peer connection to the local machine
Jinja2 – for rendering HTML templates
Uvicorn – for running the FastAPI application
