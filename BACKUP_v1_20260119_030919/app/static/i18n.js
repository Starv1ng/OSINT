// Translations for OSINT UI
const translations = {
  es: {
    title: "🔍 OSINT",
    subtitle: "Búsqueda de información de fuentes abiertas",
    searchLabel: "¿Quién o qué buscas?",
    searchPlaceholder: "Ej: Elon Musk, Donald Trump, una empresa...",
    searchHint: "Nombre de persona, usuario, email o empresa",
    typeLabel: "Tipo de búsqueda",
    typePerson: "👤 Persona",
    typeUsername: "👨‍💻 Usuario (redes sociales)",
    typeEmail: "📧 Email",
    typeCompany: "🏢 Empresa",
    typeGeneral: "🌐 General",
    typeHint: "Selecciona el tipo de búsqueda más apropiado",
    depthLabel: "Profundidad de búsqueda",
    depthHint: "1 = superficial, 3 = profunda",
    countriesLabel: "Países prioritarios (opcional)",
    countriesHint: "Deja vacío para búsqueda global, o selecciona uno o más países",
    searchButton: "🚀 Iniciar búsqueda",
    searching: "Buscando información... esto puede tardar unos segundos",
    emptyError: "Por favor, ingresa algo para buscar",
    searchError: "Error en la búsqueda",
    redirecting: "Búsqueda iniciada. Redirigiendo...",
    noJobId: "Error: no se obtuvo ID de búsqueda",
    examples: "📌 Búsquedas de ejemplo:",
    language: "Idioma",
    advancedOptions: "⚙️ Opciones avanzadas"
  },
  en: {
    title: "🔍 OSINT",
    subtitle: "Open source intelligence search",
    searchLabel: "Who or what are you looking for?",
    searchPlaceholder: "E.g: Elon Musk, Donald Trump, a company...",
    searchHint: "Name of person, username, email or company",
    typeLabel: "Search type",
    typePerson: "👤 Person",
    typeUsername: "👨‍💻 Username (social media)",
    typeEmail: "📧 Email",
    typeCompany: "🏢 Company",
    typeGeneral: "🌐 General",
    typeHint: "Select the most appropriate search type",
    depthLabel: "Search depth",
    depthHint: "1 = shallow, 3 = deep",
    countriesLabel: "Priority countries (optional)",
    countriesHint: "Leave empty for global search, or select one or more countries",
    searchButton: "🚀 Start search",
    searching: "Searching information... this may take a few seconds",
    emptyError: "Please enter something to search",
    searchError: "Search error",
    redirecting: "Search started. Redirecting...",
    noJobId: "Error: no search ID obtained",
    examples: "📌 Example searches:",
    language: "Language",
    advancedOptions: "⚙️ Advanced options"
  },
  ru: {
    title: "🔍 OSINT",
    subtitle: "Поиск информации из открытых источников",
    searchLabel: "Кого или что вы ищете?",
    searchPlaceholder: "Пример: Илон Маск, Дональд Трамп, компания...",
    searchHint: "Имя человека, имя пользователя, email или компания",
    typeLabel: "Тип поиска",
    typePerson: "👤 Человек",
    typeUsername: "👨‍💻 Пользователь (соцсети)",
    typeEmail: "📧 Email",
    typeCompany: "🏢 Компания",
    typeGeneral: "🌐 Общий",
    typeHint: "Выберите наиболее подходящий тип поиска",
    depthLabel: "Глубина поиска",
    depthHint: "1 = поверхностный, 3 = глубокий",
    countriesLabel: "Приоритетные страны (опционально)",
    countriesHint: "Оставьте пустым для глобального поиска или выберите одну или несколько стран",
    searchButton: "🚀 Начать поиск",
    searching: "Ищем информацию... это может занять несколько секунд",
    emptyError: "Пожалуйста, введите что-нибудь для поиска",
    searchError: "Ошибка поиска",
    redirecting: "Поиск начат. Перенаправление...",
    noJobId: "Ошибка: не получен ID поиска",
    examples: "📌 Примеры поисков:",
    language: "Язык",
    advancedOptions: "⚙️ Дополнительные опции"
  }
};

// Country list
const countries = {
  es: [
    { code: "US", name: "Estados Unidos" },
    { code: "ES", name: "España" },
    { code: "MX", name: "México" },
    { code: "AR", name: "Argentina" },
    { code: "BR", name: "Brasil" },
    { code: "GB", name: "Reino Unido" },
    { code: "DE", name: "Alemania" },
    { code: "FR", name: "Francia" },
    { code: "IT", name: "Italia" },
    { code: "RU", name: "Rusia" },
    { code: "CN", name: "China" },
    { code: "JP", name: "Japón" },
    { code: "IN", name: "India" },
    { code: "CA", name: "Canadá" },
    { code: "AU", name: "Australia" }
  ],
  en: [
    { code: "US", name: "United States" },
    { code: "ES", name: "Spain" },
    { code: "MX", name: "Mexico" },
    { code: "AR", name: "Argentina" },
    { code: "BR", name: "Brazil" },
    { code: "GB", name: "United Kingdom" },
    { code: "DE", name: "Germany" },
    { code: "FR", name: "France" },
    { code: "IT", name: "Italy" },
    { code: "RU", name: "Russia" },
    { code: "CN", name: "China" },
    { code: "JP", name: "Japan" },
    { code: "IN", name: "India" },
    { code: "CA", name: "Canada" },
    { code: "AU", name: "Australia" }
  ],
  ru: [
    { code: "US", name: "США" },
    { code: "ES", name: "Испания" },
    { code: "MX", name: "Мексика" },
    { code: "AR", name: "Аргентина" },
    { code: "BR", name: "Бразилия" },
    { code: "GB", name: "Великобритания" },
    { code: "DE", name: "Германия" },
    { code: "FR", name: "Франция" },
    { code: "IT", name: "Италия" },
    { code: "RU", name: "Россия" },
    { code: "CN", name: "Китай" },
    { code: "JP", name: "Япония" },
    { code: "IN", name: "Индия" },
    { code: "CA", name: "Канада" },
    { code: "AU", name: "Австралия" }
  ]
};

// Language manager
class LanguageManager {
  constructor() {
    this.currentLanguage = localStorage.getItem('language') || 'es';
  }

  setLanguage(lang) {
    if (translations[lang]) {
      this.currentLanguage = lang;
      localStorage.setItem('language', lang);
      this.updateUI();
    }
  }

  get(key) {
    return translations[this.currentLanguage][key] || key;
  }

  getCountries() {
    return countries[this.currentLanguage] || countries.en;
  }

  updateUI() {
    // This will be called after DOM is ready
    const elements = document.querySelectorAll('[data-i18n]');
    elements.forEach(el => {
      const key = el.getAttribute('data-i18n');
      el.textContent = this.get(key);
    });

    const placeholders = document.querySelectorAll('[data-i18n-placeholder]');
    placeholders.forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      el.placeholder = this.get(key);
    });

    const optionLabels = document.querySelectorAll('[data-i18n-select]');
    optionLabels.forEach(el => {
      const key = el.getAttribute('data-i18n-select');
      el.textContent = this.get(key);
    });

    // Update countries dropdown
    this.updateCountriesDropdown();
  }

  updateCountriesDropdown() {
    const select = document.getElementById('countries');
    if (!select) return;

    const currentValues = Array.from(select.selectedOptions).map(o => o.value);
    select.innerHTML = '';

    this.getCountries().forEach(country => {
      const option = document.createElement('option');
      option.value = country.code;
      option.textContent = `${country.name} (${country.code})`;
      option.selected = currentValues.includes(country.code);
      select.appendChild(option);
    });
  }
}

// Create global instance
const i18n = new LanguageManager();
