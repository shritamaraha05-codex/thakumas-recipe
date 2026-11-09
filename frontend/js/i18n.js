// i18n.js — Unified bilingual internationalisation module for Thakuma's Recipe

export const STORAGE_KEY = 'thakuma_language';
export const LEGACY_STORAGE_KEY = 'thakuma-language';

export const translations = {
  bn: {
    // Navigation
    nav: {
      brand: 'ঠাকুমার রান্না',
      brandCaption: 'ঘরের স্বাদ',
      recipes: 'রেসিপি',
      record: 'নতুন রেসিপি',
      cook: 'রান্না মোড',
      herHand: 'হাতের মাপ',
      accuracy: 'নির্ভুলতা',
      profile: 'প্রোফাইল',
      signIn: 'লগইন',
      signOut: 'লগআউট',
      home: 'হোম',
      installApp: 'অ্যাপ ইনস্টল'
    },

    // Common UI terms
    common: {
      save: 'সংরক্ষণ করুন',
      saved: 'সংরক্ষিত হয়েছে',
      cancel: 'বাতিল',
      back: 'ফিরে যান',
      retry: 'আবার চেষ্টা করুন',
      loading: 'লোড হচ্ছে…',
      error: 'সমস্যা হয়েছে',
      offline: 'অফলাইন',
      delete: 'মুছে ফেলুন',
      edit: 'সম্পাদনা',
      confirm: 'নিশ্চিত করুন',
      close: 'বন্ধ করুন',
      installMobile: 'অ্যাপ ইনস্টল করুন'
    },

    // Profile Page Keys (supports both flat and nested lookups)
    profile: {
      brand: 'ঠাকুমার রান্না',
      brandCaption: 'ঘরের স্বাদ',
      navRecipes: 'রেসিপি',
      navHands: 'হাতের মাপ',
      navAccuracy: 'নির্ভুলতা',
      breadcrumbHome: 'হোম (রেসিপি খাতা)',
      breadcrumbProfile: 'প্রোফাইল',
      eyebrow: 'আপনার নিজের জায়গা',
      pageTitle: 'আমার প্রোফাইল',
      pageDescription: 'আপনার রান্নার খাতাটি নিজের মতো করে সাজিয়ে নিন। প্রয়োজনীয় তথ্য আর পছন্দ—শুধু এইটুকুই।',
      profileKicker: 'ব্যক্তিগত প্রোফাইল',
      profileNameFallback: 'আপনার নাম',
      profileEmailFallback: 'আপনার ইমেল এখানে দেখা যাবে',
      detailsTitle: 'ব্যক্তিগত তথ্য',
      detailsDescription: 'আপনার প্রোফাইলে যে নাম ও তথ্য দেখানো হবে, তা এখানে লিখুন।',
      nameLabel: 'আপনার নাম',
      emailLabel: 'ইমেল ঠিকানা',
      kitchenLabel: 'রান্নাঘর বা পরিবারের নাম',
      namePlaceholder: 'আপনার নাম লিখুন',
      emailPlaceholder: 'আপনার ইমেল ঠিকানা',
      kitchenPlaceholder: 'যেমন: রায় বাড়ির হেঁশেল',
      saveButton: 'পরিবর্তন সংরক্ষণ',
      saveProfile: 'পরিবর্তন সংরক্ষণ',
      saveNote: 'এই পৃষ্ঠার তথ্য আপনার অ্যাকাউন্ট ও প্রোফাইলে সুরক্ষিত থাকবে।',
      preferencesEyebrow: 'পরিমাপের ধরন',
      preferencesTitle: 'রান্নার পছন্দ',
      preferencesDescription: 'রেসিপিতে উপকরণের মাপ কীভাবে দেখতে চান?',
      unitsTitle: 'রান্নার পছন্দ',
      unitsDescription: 'রেসিপিতে উপকরণের মাপ কীভাবে দেখতে চান?',
      unitsLabel: 'পরিমাপের ধরন',
      traditionalTitle: 'ঐতিহ্যবাহী মাপ',
      traditionalDescription: 'মুঠো, চিমটি ও হাতের আন্দাজ',
      metricTitle: 'মেট্রিক মাপ',
      metricDescription: 'গ্রাম, কিলোগ্রাম ও মিলিলিটার',
      languageHintTitle: 'ভাষা বদলাতে',
      languageHint: 'পাতার একেবারে উপরের বাংলা / EN সুইচটি ব্যবহার করুন। আপনার পছন্দ মনে রাখা হবে।',
      bottomNote: 'আপনার প্রোফাইল হালকা ও সহজ রাখা হয়েছে—রেসিপি, হাতের মাপ ও রান্নার অভিজ্ঞতাই থাকুক মূল জায়গায়।',
      backToRecipes: 'রেসিপিতে ফিরে যান ↗',
      copyright: ' · রান্নার স্মৃতি, যত্নে রাখা',
      profileSaved: 'প্রোফাইলের তথ্য সংরক্ষিত হয়েছে।',
      unitSavedTraditional: 'ঐতিহ্যবাহী পরিমাপ নির্বাচন করা হলো।',
      unitSavedMetric: 'মেট্রিক পরিমাপ নির্বাচন করা হলো।',
      logoutText: 'লগআউট (Log out)'
    },

    // Login & Registration
    login: {
      brand: 'ঠাকুমার রান্না',
      brandCaption: 'ঘরের স্বাদ',
      navHome: 'হোম',
      tagline: 'আপনার পরিবার। আপনার রেসিপি। আপনার স্মৃতি।',
      bengaliLine: 'প্রজন্মের পর প্রজন্ম ধরে<br />রান্নার গল্প এখন আপনার হাতে।',
      emailButton: 'ইমেল দিয়ে এগিয়ে যান',
      googleButton: 'Google দিয়ে এগিয়ে যান',
      accountPrompt: 'আগে থেকেই অ্যাকাউন্ট আছে?',
      login: 'লগইন করুন',
      back: '← ফিরে যান',
      nameLabel: 'আপনার নাম',
      kitchenLabel: 'পারিবারিক রান্নাঘরের নাম',
      identifierLabel: 'ইমেইল অ্যাড্রেস',
      passwordLabel: 'পাসওয়ার্ড',
      namePlaceholder: 'যেমন: অনন্যা সেন',
      kitchenPlaceholder: 'যেমন: রায় বাড়ির হেঁশেল',
      identifierPlaceholder: 'ইমেইল লিখুন (name@example.com)',
      passwordPlaceholder: 'কমপক্ষে ৬টি অক্ষর',
      forgot: 'পাসওয়ার্ড ভুলে গেছেন?',
      remember: 'এই ডিভাইসে আমার খাতা মনে রাখুন',
      guest: 'অতিথি হিসেবে দেখুন · ডেমো',
      formSwitchSignup: 'ঠাকুমার রান্নায় নতুন?',
      formSwitchCreate: 'নতুন অ্যাকাউন্ট খুলুন',
      formSwitchLogin: 'লগইন করুন',
      googleNotice: 'Google দিয়ে সাইন ইন করতে Supabase প্রকল্পে OAuth কনফিগারেশন প্রয়োজন।',
      resetNotice: 'পাসওয়ার্ড রিসেটের লিংক আপনার ইমেইলে পাঠানোর ব্যবস্থা করা হচ্ছে।',
      missingIdentifier: 'দয়া করে একটি সঠিক ইমেইল ঠিকানা লিখুন।',
      shortPassword: 'কমপক্ষে ৬ অক্ষরের পাসওয়ার্ড লিখুন।',
      signingIn: 'লগইন করা হচ্ছে…',
      signingUp: 'খাতা তৈরি করা হচ্ছে…',
      signupSuccess: 'খাতা সফলভাবে তৈরি হয়েছে! প্রবেশ করা হচ্ছে…',
      signupConfirm: 'অ্যাকাউন্ট তৈরি হয়েছে। আপনার ইমেইল যাচাই করে লগইন করুন।',
      unconfiguredNotice: 'Supabase কনফিগারেশন কী অনুপস্থিত (VITE_SUPABASE_URL / VITE_SUPABASE_PUBLISHABLE_KEY)।'
    },

    // Recipe Library
    library: {
      notice: 'ঠাকুমার হাতের মাপজোখ: স্মৃতি থেকে স্বাদ, প্রতিটি পদে নিজের গল্প।',
      eyebrow: 'ঠাকুমার পারিবারিক রন্ধন খাতা',
      pageTitle: 'আপনার রেসিপি',
      pageSub: 'ঠাকুমার ঘরের স্বাদ, এবার আপনার রান্নাঘরে।',
      searchPlaceholder: 'রেসিপির নাম খুঁজুন...',
      addRecipe: 'নতুন পদ',
      savedCount: 'সংরক্ষিত রেসিপি',
      heirloomArchive: 'পারিবারিক রন্ধন খাতা',
      spokenRecipes: 'মুখে মুখে শেখা পদ',
      herWords: 'স্মৃতি থেকে স্বাদের খাতা',
      filterAll: 'সব পদ',
      noRecipes: 'কোনো রেসিপি পাওয়া যায়নি',
      noRecipesSub: 'আপনার খাতা এখনো খালি। ঠাকুমার স্মৃতি ও রান্না ধরে রাখতে প্রথম রেসিপিটি যোগ করুন।',
      recordFirst: 'প্রথম রেসিপি যোগ করুন',
      serverError: 'রেসিপি লোড করতে সমস্যা হয়েছে',
      retry: 'আবার চেষ্টা করুন'
    },

    // Record Recipe
    record: {
      pageTitle: 'রেসিপি সংরক্ষণ',
      stepVoice: '১. মুখে বলুন',
      stepParse: '২. হাতের মাপ যাচাই',
      stepSave: '৩. খাতায় রাখুন',
      narrationPlaceholder: 'ঠাকুমা যেভাবে শিখিয়েছেন, ঠিক সেভাবেই বলুন… (যেমন: এক মুঠো চাল, এক চিমটি নুন, সামান্য হলুদ দিয়ে সেদ্ধ বসাও…)',
      parseBtn: 'মাপজোখ বিশ্লেষণ করুন',
      saveRecipeBtn: 'রেসিপি সংরক্ষণ করুন'
    },

    // Recipe Detail
    recipeDetail: {
      backToLibrary: '← রেসিপি তালিকায় ফিরুন',
      ingredients: 'উপকরণ ও হাতের মাপ',
      steps: 'প্রণালী',
      originalStory: 'ঠাকুমার নিজের কথা',
      startCookMode: 'রান্না শুরু করুন (হ্যান্ডস-ফ্রি)',
      deleteRecipe: 'রেসিপি মুছুন'
    },

    // Cook Mode
    cookMode: {
      title: 'রান্না মোড',
      step: 'ধাপ',
      startTimer: 'টাইমার শুরু',
      pauseTimer: 'বিরতি',
      resetTimer: 'রিসেট',
      nextStep: 'পরবর্তী ধাপ',
      prevStep: 'আগের ধাপ',
      finishCooking: 'রান্না সমাপ্ত'
    }
  },

  en: {
    // Navigation
    nav: {
      brand: "Thakuma's Recipe",
      brandCaption: 'A taste of home',
      recipes: 'Recipes',
      record: 'Add Recipe',
      cook: 'Cook Mode',
      herHand: 'Her Hand',
      accuracy: 'Accuracy',
      profile: 'Profile',
      signIn: 'Sign in',
      signOut: 'Log out',
      home: 'Home',
      installApp: 'Install App'
    },

    // Common UI terms
    common: {
      save: 'Save',
      saved: 'Saved',
      cancel: 'Cancel',
      back: 'Back',
      retry: 'Retry',
      loading: 'Loading…',
      error: 'An error occurred',
      offline: 'Offline',
      delete: 'Delete',
      edit: 'Edit',
      confirm: 'Confirm',
      close: 'Close',
      installMobile: 'Install App'
    },

    // Profile Page Keys
    profile: {
      brand: "Thakuma's Recipe",
      brandCaption: 'A taste of home',
      navRecipes: 'Recipes',
      navHands: 'Her Hand',
      navAccuracy: 'Accuracy',
      breadcrumbHome: 'Home (Library)',
      breadcrumbProfile: 'Profile',
      eyebrow: 'YOUR PERSONAL SPACE',
      pageTitle: 'My Profile',
      pageDescription: 'Personalize your kitchen notebook with simple preferences and essential information.',
      profileKicker: 'PERSONAL PROFILE',
      profileNameFallback: 'Your Name',
      profileEmailFallback: 'Your email will appear here',
      detailsTitle: 'Personal Details',
      detailsDescription: 'Keep your identity and household details up to date across your recipe archive.',
      nameLabel: 'Your name',
      emailLabel: 'Email address',
      kitchenLabel: 'Family kitchen name',
      namePlaceholder: 'Enter your name',
      emailPlaceholder: 'you@example.com',
      kitchenPlaceholder: 'e.g. The Sen Family Kitchen',
      saveButton: 'Save changes',
      saveProfile: 'Save changes',
      saveNote: 'Your profile details are securely saved with your account.',
      preferencesEyebrow: 'JUST THE ESSENTIALS',
      preferencesTitle: 'Cooking Preferences',
      preferencesDescription: 'Choose how ingredient quantities should be displayed by default.',
      unitsTitle: 'Cooking Preferences',
      unitsDescription: 'Choose how ingredient quantities should be displayed by default.',
      unitsLabel: 'Measurement System',
      traditionalTitle: 'Traditional Bengali measures',
      traditionalDescription: 'Mutho, chimti and hand-measured intuition',
      metricTitle: 'Metric units',
      metricDescription: 'Grams, kilograms and millilitres',
      languageHintTitle: 'To switch language',
      languageHint: 'Use the বাংলা / EN switch in the top navigation bar. Your choice is saved.',
      bottomNote: 'Your profile keeps things simple—her recipes, hand measures and cooking memory remain the focus.',
      backToRecipes: 'Back to recipes ↗',
      copyright: ' · Preserving family recipes with love',
      profileSaved: 'Profile details saved successfully.',
      unitSavedTraditional: 'Traditional Bengali measures selected.',
      unitSavedMetric: 'Metric units selected.',
      logoutText: 'Log out'
    },

    // Login & Registration
    login: {
      brand: "Thakuma's Recipe",
      brandCaption: 'A taste of home',
      navHome: 'Home',
      tagline: 'Your family. Your recipes. Your memories.',
      bengaliLine: 'Generations of family recipes,<br />kept close and passed on with love.',
      emailButton: 'Continue with Email',
      googleButton: 'Continue with Google',
      accountPrompt: 'Already have an account?',
      login: 'Log in',
      back: '← Back',
      nameLabel: 'Your name',
      kitchenLabel: 'Family kitchen name',
      identifierLabel: 'Email address',
      passwordLabel: 'Password',
      namePlaceholder: 'e.g. Ananya Sen',
      kitchenPlaceholder: 'e.g. The Sen family kitchen',
      identifierPlaceholder: 'Enter email (name@example.com)',
      passwordPlaceholder: 'At least 6 characters',
      forgot: 'Forgot password?',
      remember: 'Remember my kitchen on this device',
      guest: 'Explore as a guest · Demo',
      formSwitchSignup: "New to Thakuma's kitchen?",
      formSwitchCreate: 'Create an account',
      formSwitchLogin: 'Log in',
      googleNotice: 'Google sign-in requires Google OAuth to be enabled in Supabase.',
      resetNotice: 'Password reset instructions will be sent to your email.',
      missingIdentifier: 'Please enter a valid email address.',
      shortPassword: 'Please enter a password with at least 6 characters.',
      signingIn: 'Signing in…',
      signingUp: 'Creating account…',
      signupSuccess: 'Account created! Redirecting to recipe library…',
      signupConfirm: 'Account created! Please check your email to verify before logging in.',
      unconfiguredNotice: 'Supabase environment variables are missing (VITE_SUPABASE_URL / VITE_SUPABASE_PUBLISHABLE_KEY).'
    },

    // Recipe Library
    library: {
      notice: 'Her measures, your memories — every recipe keeps its own story.',
      eyebrow: 'THE FAMILY RECIPE ARCHIVE',
      pageTitle: 'Your Recipes',
      pageSub: 'The flavours of her kitchen, now in yours.',
      searchPlaceholder: 'Search your recipes...',
      addRecipe: 'Add recipe',
      savedCount: 'Saved recipes',
      heirloomArchive: 'Family heirloom archive',
      spokenRecipes: 'Spoken recipes',
      herWords: 'Captured in her own words',
      filterAll: 'All Recipes',
      noRecipes: 'No recipes found',
      noRecipesSub: 'Your archive is currently empty. Record your first family recipe to begin.',
      recordFirst: 'Record first recipe',
      serverError: 'Could not load recipes',
      retry: 'Retry'
    },

    // Record Recipe
    record: {
      pageTitle: 'Preserve a Recipe',
      stepVoice: '1. Tell the recipe',
      stepParse: '2. Review hand measures',
      stepSave: '3. Save to notebook',
      narrationPlaceholder: 'Tell the recipe as she taught you… (e.g., Take a handful of rice, a pinch of salt, a dash of turmeric…)',
      parseBtn: 'Analyze & Parse',
      saveRecipeBtn: 'Save Recipe'
    },

    // Recipe Detail
    recipeDetail: {
      backToLibrary: '← Back to recipes',
      ingredients: 'Ingredients & Measures',
      steps: 'Cooking Instructions',
      originalStory: 'In Her Own Words',
      startCookMode: 'Start Cooking (Hands-free)',
      deleteRecipe: 'Delete Recipe'
    },

    // Cook Mode
    cookMode: {
      title: 'Cook Mode',
      step: 'Step',
      startTimer: 'Start Timer',
      pauseTimer: 'Pause Timer',
      resetTimer: 'Reset',
      nextStep: 'Next Step',
      prevStep: 'Previous Step',
      finishCooking: 'Finish Cooking'
    }
  }
};

/**
 * Get current language ('en' or 'bn'). Defaults to 'en' when not set.
 */
export function getLanguage() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY) || localStorage.getItem(LEGACY_STORAGE_KEY);
    return saved === 'bn' ? 'bn' : 'en';
  } catch {
    return 'en';
  }
}

/**
 * Set and persist preferred language, updating DOM and dispatching languagechange event.
 */
export function setLanguage(lang) {
  const normalized = lang === 'bn' ? 'bn' : 'en';
  try {
    localStorage.setItem(STORAGE_KEY, normalized);
    localStorage.setItem(LEGACY_STORAGE_KEY, normalized);
  } catch {}

  applyI18n();

  // Dispatch custom event for dynamic re-renders
  window.dispatchEvent(new CustomEvent('languagechange', { detail: { language: normalized } }));
  return normalized;
}

/**
 * Backward compatibility alias for setLanguage
 */
export function setPreferredLanguage(lang) {
  return setLanguage(lang);
}

/**
 * Backward compatibility alias for getLanguage
 */
export function getPreferredLanguage() {
  return getLanguage();
}

/**
 * Translate a key string (supports flat keys like 'saveButton' and dotted paths like 'nav.recipes').
 */
export function t(key, fallback = '') {
  if (!key) return fallback;
  const lang = getLanguage();
  const dict = translations[lang] || translations.en;

  // 1. Direct key match (top-level or flat key in profile/login/common)
  if (dict[key] !== undefined) return dict[key];

  // 2. Nested dot lookup (e.g., 'nav.recipes' or 'profile.detailsTitle')
  if (key.includes('.')) {
    const parts = key.split('.');
    let cur = dict;
    for (const p of parts) {
      if (cur && cur[p] !== undefined) cur = cur[p];
      else { cur = undefined; break; }
    }
    if (cur !== undefined && typeof cur === 'string') return cur;
  }

  // 3. Search common namespaces (profile, common, nav, login, library)
  for (const ns of ['profile', 'nav', 'common', 'login', 'library', 'record', 'cookMode', 'recipeDetail']) {
    if (dict[ns] && dict[ns][key] !== undefined) {
      return dict[ns][key];
    }
  }

  // 4. Fallback to English dictionary if currently in Bengali
  if (lang !== 'en') {
    const enDict = translations.en;
    if (enDict[key] !== undefined) return enDict[key];
    for (const ns of ['profile', 'nav', 'common', 'login', 'library', 'record', 'cookMode', 'recipeDetail']) {
      if (enDict[ns] && enDict[ns][key] !== undefined) {
        return enDict[ns][key];
      }
    }
  }

  return fallback || key;
}

/**
 * Apply current language translations to all elements in the given root (default document).
 */
export function applyI18n(root = document) {
  const currentLang = getLanguage();

  // 1. Update html lang attribute and classes on html & body
  document.documentElement.lang = currentLang;
  document.documentElement.classList.toggle('lang-en', currentLang === 'en');
  document.documentElement.classList.toggle('lang-bn', currentLang === 'bn');
  if (document.body) {
    document.body.classList.toggle('lang-en', currentLang === 'en');
    document.body.classList.toggle('lang-bn', currentLang === 'bn');
  }

  // 2. Handle data-i18n attributes
  root.querySelectorAll('[data-i18n]').forEach((el) => {
    const key = el.dataset.i18n;
    const translated = t(key);
    if (translated) {
      if (translated.includes('<') && translated.includes('>')) {
        el.innerHTML = translated;
      } else {
        el.textContent = translated;
      }
    }
  });

  // 3. Handle data-i18n-placeholder
  root.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
    const key = el.dataset.i18nPlaceholder;
    const translated = t(key);
    if (translated) el.placeholder = translated;
  });

  // 4. Handle data-placeholder-en / data-placeholder-bn
  root.querySelectorAll('[data-placeholder-en]').forEach((input) => {
    input.placeholder = currentLang === 'en' ? input.dataset.placeholderEn : input.dataset.placeholderBn;
  });

  // 5. Handle data-ph-bn / data-ph-en
  root.querySelectorAll('[data-ph-bn]').forEach((input) => {
    input.placeholder = currentLang === 'en' ? (input.dataset.phEn || input.dataset.phBn) : input.dataset.phBn;
  });

  // 6. Handle data-bn & data-en pairs
  root.querySelectorAll('[data-bn]').forEach((el) => {
    const target = el.dataset[currentLang] || el.dataset.bn;
    if (target !== undefined) {
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.value = target;
      } else if (target.includes('<') && target.includes('>')) {
        el.innerHTML = target;
      } else {
        el.textContent = target;
      }
    }
  });

  // 7. Handle data-i18n-title & data-i18n-aria
  root.querySelectorAll('[data-i18n-title]').forEach((el) => {
    const translated = t(el.dataset.i18nTitle);
    if (translated) el.title = translated;
  });
  root.querySelectorAll('[data-i18n-aria]').forEach((el) => {
    const translated = t(el.dataset.i18nAria);
    if (translated) el.setAttribute('aria-label', translated);
  });

  // 8. Handle explicit .bn and .en visibility spans
  root.querySelectorAll('.bn').forEach((el) => {
    // Only toggle if not part of user-content / audio
    if (!el.closest('.user-content, .recipe-body, #transcriptDisplay')) {
      el.style.display = currentLang === 'bn' ? '' : 'none';
    }
  });
  root.querySelectorAll('.en').forEach((el) => {
    if (!el.closest('.user-content, .recipe-body, #transcriptDisplay')) {
      el.style.display = currentLang === 'en' ? '' : 'none';
    }
  });

  // 9. Sync all language buttons across the DOM
  root.querySelectorAll('.lang-btn, .language-switch button, .lang button, [data-language], [data-l], [data-lang]').forEach((btn) => {
    const btnLang = btn.dataset.language || btn.dataset.l || btn.dataset.lang;
    if (!btnLang) return;
    const isActive = btnLang === currentLang;
    btn.setAttribute('aria-pressed', String(isActive));
    btn.classList.toggle('active', isActive);
    btn.classList.toggle('on', isActive);
    btn.classList.toggle('selected', isActive);
  });
}

/**
 * Initialize internationalization system on the page.
 */
export function initI18n() {
  applyI18n();

  // Attach click listener to all language switches
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.lang-btn, .language-switch button, .lang button, [data-language], [data-l], [data-lang]');
    if (!btn) return;
    const targetLang = btn.dataset.language || btn.dataset.l || btn.dataset.lang;
    if (targetLang && (targetLang === 'en' || targetLang === 'bn')) {
      e.preventDefault();
      setLanguage(targetLang);
    }
  });

  // Sync across tabs
  window.addEventListener('storage', (e) => {
    if (e.key === STORAGE_KEY || e.key === LEGACY_STORAGE_KEY) {
      applyI18n();
      window.dispatchEvent(new CustomEvent('languagechange', { detail: { language: getLanguage() } }));
    }
  });
}

