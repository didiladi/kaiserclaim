// kc-app.jsx — App shell, router, mock data, state management

// ═══════════════════════════════════════════════════════════════
// FAMILY MEMBERS
// ═══════════════════════════════════════════════════════════════

const FAMILY_MEMBERS = [
  { id: 'all', name: 'Alle', initials: '', color: '#6B7280' },
  { id: 'maria', name: 'Maria', initials: 'MK', color: '#E84393' },
  { id: 'thomas', name: 'Thomas', initials: 'TK', color: '#3B82F6' },
  { id: 'luisa', name: 'Luisa', initials: 'LK', color: '#F59E0B' },
  { id: 'felix', name: 'Felix', initials: 'FK', color: '#10B981' },
];

const MEMBER_COLORS = {
  maria: '#E84393', thomas: '#3B82F6', luisa: '#F59E0B', felix: '#10B981',
};

// ═══════════════════════════════════════════════════════════════
// MOCK INVOICES (multi-member)
// ═══════════════════════════════════════════════════════════════

const MOCK_INVOICES = [
  // Maria
  { id: 1, provider: 'Apotheke Zur Gesundheit', amount: 42.50, date: '15.05.2026', uploaded: '15.05.2026',
    relativeTime: 'vor 4 Tagen', status: 'bei_merkur', patient: 'Maria Kaiser', memberId: 'maria',
    category: 'Medikamente', contract: 'Merkur Sonderklasse', pipeline: 'pharmacy', currentStep: 3 },
  { id: 2, provider: 'Ordination Dr. Müller', amount: 85.00, date: '03.05.2026', uploaded: '03.05.2026',
    relativeTime: 'vor 16 Tagen', status: 'abgeschlossen', patient: 'Maria Kaiser', memberId: 'maria',
    category: 'Allgemeinmedizin', contract: 'Merkur Sonderklasse', pipeline: 'standard', currentStep: 7 },
  { id: 3, provider: 'Dr. Stefan Berger', amount: 210.00, date: '28.04.2026', uploaded: '28.04.2026',
    relativeTime: 'vor 3 Wochen', status: 'abgeschlossen', patient: 'Maria Kaiser', memberId: 'maria',
    category: 'Physiotherapie', contract: 'Merkur Sonderklasse', pipeline: 'standard', currentStep: 7 },
  { id: 11, provider: 'Apotheke Mariahilf', amount: 31.20, date: '18.02.2026', uploaded: '18.02.2026',
    relativeTime: 'vor 3 Monaten', status: 'abgeschlossen', patient: 'Maria Kaiser', memberId: 'maria',
    category: 'Medikamente', contract: 'Merkur Sonderklasse', pipeline: 'pharmacy', currentStep: 4 },
  { id: 12, provider: 'Dr. Karin Lechner', amount: 120.00, date: '10.01.2026', uploaded: '10.01.2026',
    relativeTime: 'vor 4 Monaten', status: 'abgeschlossen', patient: 'Maria Kaiser', memberId: 'maria',
    category: 'Zahnreinigung', contract: 'Merkur Sonderklasse', pipeline: 'standard', currentStep: 7 },

  // Thomas
  { id: 4, provider: 'Dr. Anna Huber', amount: 120.00, date: '10.05.2026', uploaded: '10.05.2026',
    relativeTime: 'vor 9 Tagen', status: 'von_oegk', patient: 'Thomas Kaiser', memberId: 'thomas',
    category: 'Zahnarzt', contract: 'Merkur Sonderklasse', pipeline: 'standard', currentStep: 4 },
  { id: 5, provider: 'Apotheke Mariahilf', amount: 18.90, date: '19.05.2026', uploaded: '19.05.2026',
    relativeTime: 'heute', status: 'ocr', patient: 'Thomas Kaiser', memberId: 'thomas',
    category: 'Medikamente', contract: 'Merkur Sonderklasse', pipeline: 'pharmacy', currentStep: 1 },
  { id: 6, provider: 'Physio Zentrum Wien', amount: 95.00, date: '22.04.2026', uploaded: '22.04.2026',
    relativeTime: 'vor 4 Wochen', status: 'abgeschlossen', patient: 'Thomas Kaiser', memberId: 'thomas',
    category: 'Physiotherapie', contract: 'Merkur Sonderklasse', pipeline: 'standard', currentStep: 7 },
  { id: 13, provider: 'Apotheke Zum Löwen', amount: 14.50, date: '05.03.2026', uploaded: '05.03.2026',
    relativeTime: 'vor 2 Monaten', status: 'abgeschlossen', patient: 'Thomas Kaiser', memberId: 'thomas',
    category: 'Medikamente', contract: 'Merkur Sonderklasse', pipeline: 'pharmacy', currentStep: 4 },

  // Luisa (child)
  { id: 7, provider: 'Kinderarzt Dr. Novak', amount: 65.00, date: '12.05.2026', uploaded: '12.05.2026',
    relativeTime: 'vor 7 Tagen', status: 'bei_oegk', patient: 'Luisa Kaiser', memberId: 'luisa',
    category: 'Kinderarzt', contract: 'Merkur Sonderklasse', pipeline: 'standard', currentStep: 3 },
  { id: 8, provider: 'Apotheke Zum Löwen', amount: 24.80, date: '12.05.2026', uploaded: '12.05.2026',
    relativeTime: 'vor 7 Tagen', status: 'abgeschlossen', patient: 'Luisa Kaiser', memberId: 'luisa',
    category: 'Medikamente', contract: 'Merkur Sonderklasse', pipeline: 'pharmacy', currentStep: 4 },
  { id: 14, provider: 'Kinderarzt Dr. Novak', amount: 65.00, date: '08.02.2026', uploaded: '08.02.2026',
    relativeTime: 'vor 3 Monaten', status: 'abgeschlossen', patient: 'Luisa Kaiser', memberId: 'luisa',
    category: 'Kinderarzt', contract: 'Merkur Sonderklasse', pipeline: 'standard', currentStep: 7 },

  // Felix (child)
  { id: 9, provider: 'Kinderarzt Dr. Novak', amount: 65.00, date: '08.05.2026', uploaded: '08.05.2026',
    relativeTime: 'vor 11 Tagen', status: 'abgeschlossen', patient: 'Felix Kaiser', memberId: 'felix',
    category: 'Kinderarzt', contract: 'Merkur Sonderklasse', pipeline: 'standard', currentStep: 7 },
  { id: 10, provider: 'Optiker Brillenwelt', amount: 180.00, date: '15.04.2026', uploaded: '15.04.2026',
    relativeTime: 'vor 5 Wochen', status: 'abgeschlossen', patient: 'Felix Kaiser', memberId: 'felix',
    category: 'Sehbehelfe', contract: 'Merkur Sonderklasse', pipeline: 'standard', currentStep: 7 },
  { id: 15, provider: 'Apotheke Mariahilf', amount: 12.30, date: '20.03.2026', uploaded: '20.03.2026',
    relativeTime: 'vor 2 Monaten', status: 'abgeschlossen', patient: 'Felix Kaiser', memberId: 'felix',
    category: 'Medikamente', contract: 'Merkur Sonderklasse', pipeline: 'pharmacy', currentStep: 4 },
];

// ═══════════════════════════════════════════════════════════════
// MOCK BENEFITS (per-member)
// ═══════════════════════════════════════════════════════════════

const MOCK_BENEFITS = [
  {
    contract: 'Merkur Sonderklasse',
    policyNumber: 'MS-2024-78912',
    members: [
      {
        memberId: 'maria', name: 'Maria Kaiser',
        benefits: [
          { name: 'Zahnreinigung', used: 120, limit: 150, period: 'jährlich' },
          { name: 'Physiotherapie', used: 450, limit: 800, period: 'jährlich' },
          { name: 'Allgemeinmedizin', used: 280, limit: 1200, period: 'jährlich' },
          { name: 'Medikamente', used: 95, limit: 500, period: 'jährlich' },
          { name: 'Sehbehelfe', used: 0, limit: 200, period: '2-jährlich' },
        ],
      },
      {
        memberId: 'thomas', name: 'Thomas Kaiser',
        benefits: [
          { name: 'Zahnreinigung', used: 80, limit: 150, period: 'jährlich' },
          { name: 'Physiotherapie', used: 190, limit: 800, period: 'jährlich' },
          { name: 'Allgemeinmedizin', used: 120, limit: 1200, period: 'jährlich' },
          { name: 'Medikamente', used: 62, limit: 500, period: 'jährlich' },
          { name: 'Sehbehelfe', used: 0, limit: 200, period: '2-jährlich' },
        ],
      },
      {
        memberId: 'luisa', name: 'Luisa Kaiser',
        benefits: [
          { name: 'Kinderarzt', used: 130, limit: 400, period: 'jährlich' },
          { name: 'Medikamente', used: 48, limit: 300, period: 'jährlich' },
          { name: 'Sehbehelfe', used: 0, limit: 200, period: '2-jährlich' },
        ],
      },
      {
        memberId: 'felix', name: 'Felix Kaiser',
        benefits: [
          { name: 'Kinderarzt', used: 195, limit: 400, period: 'jährlich' },
          { name: 'Medikamente', used: 35, limit: 300, period: 'jährlich' },
          { name: 'Sehbehelfe', used: 180, limit: 200, period: '2-jährlich' },
        ],
      },
    ],
  },
];

// ═══════════════════════════════════════════════════════════════
// MOCK MONTHLY STATS
// ═══════════════════════════════════════════════════════════════

const MOCK_MONTHLY_2026 = [
  { month: 'Jan', total: 145.00, members: { maria: 120, thomas: 25, luisa: 0, felix: 0 } },
  { month: 'Feb', total: 316.20, members: { maria: 31.20, thomas: 95, luisa: 130, felix: 60 } },
  { month: 'Mär', total: 226.80, members: { maria: 0, thomas: 14.50, luisa: 0, felix: 212.30 } },
  { month: 'Apr', total: 485.00, members: { maria: 210, thomas: 95, luisa: 0, felix: 180 } },
  { month: 'Mai', total: 421.20, members: { maria: 127.50, thomas: 138.90, luisa: 89.80, felix: 65 } },
];

const MOCK_YEARLY = [
  { year: '2024', paid: 3240, reimbursed: 2890 },
  { year: '2025', paid: 4120, reimbursed: 3780 },
  { year: '2026', paid: 1594.20, reimbursed: 1247.50 },
];

// ═══════════════════════════════════════════════════════════════
// APP SHELL + ROUTER
// ═══════════════════════════════════════════════════════════════

function KaiserClaimApp({ darkMode = false, accentColor = '#0D9488' }) {
  const [loggedIn, setLoggedIn] = useState(true);
  const [screen, setScreen] = useState('home');
  const [activeTab, setActiveTab] = useState('home');
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [history, setHistory] = useState([]);
  const [activeMember, setActiveMember] = useState('all');

  const navigate = (s, opts = {}) => {
    if (!opts.replace) setHistory(h => [...h, screen]);
    setScreen(s);
    if (['home', 'invoices', 'benefits', 'stats', 'settings'].includes(s)) setActiveTab(s);
  };
  const goBack = () => {
    const prev = history[history.length - 1] || 'home';
    setHistory(h => h.slice(0, -1));
    setScreen(prev);
    if (['home', 'invoices', 'benefits', 'stats', 'settings'].includes(prev)) setActiveTab(prev);
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setScreen(tab);
    setHistory([]);
  };

  const handleInvoice = (id) => {
    setSelectedInvoice(MOCK_INVOICES.find(i => i.id === id));
    navigate('detail');
  };

  // Filter invoices by member
  const filteredInvoices = activeMember === 'all'
    ? MOCK_INVOICES
    : MOCK_INVOICES.filter(i => i.memberId === activeMember);

  const showShell = loggedIn && !['upload', 'detail', 'onboarding'].includes(screen);
  const showBack = ['upload', 'detail', 'onboarding'].includes(screen);
  const backTitles = { upload: 'Beleg hochladen', detail: 'Belegdetails', onboarding: 'Neuer Vertrag' };

  if (!loggedIn) {
    return (
      <ThemeCtx.Provider value={{ dark: darkMode, accent: accentColor }}>
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          <LoginScreen onLogin={() => { setLoggedIn(true); setScreen('home'); }}/>
        </div>
      </ThemeCtx.Provider>
    );
  }

  const renderScreen = () => {
    switch (screen) {
      case 'home':
        return <HomeScreen
          invoices={MOCK_INVOICES} benefits={MOCK_BENEFITS}
          familyMembers={FAMILY_MEMBERS} activeMember={activeMember}
          onMemberChange={setActiveMember}
          onInvoice={handleInvoice}
          onUpload={() => navigate('upload')}
          onViewAll={() => handleTabChange('invoices')}
          onBenefits={() => handleTabChange('benefits')}
          onStats={() => handleTabChange('stats')}
        />;
      case 'invoices':
        return <InvoiceListScreen
          invoices={MOCK_INVOICES}
          familyMembers={FAMILY_MEMBERS} activeMember={activeMember}
          onMemberChange={setActiveMember}
          onInvoice={handleInvoice}
        />;
      case 'detail':
        return <InvoiceDetailScreen invoice={selectedInvoice} onBack={goBack}/>;
      case 'upload':
        return <UploadScreen onBack={goBack} onSuccess={() => { navigate('invoices', { replace: true }); }}
          familyMembers={FAMILY_MEMBERS.filter(m => m.id !== 'all')}/>;
      case 'benefits':
        return <BenefitsScreen benefits={MOCK_BENEFITS}
          familyMembers={FAMILY_MEMBERS} activeMember={activeMember}
          onMemberChange={setActiveMember}
          onAddContract={() => navigate('onboarding')}/>;
      case 'stats':
        return <StatsScreen
          invoices={MOCK_INVOICES} monthly={MOCK_MONTHLY_2026} yearly={MOCK_YEARLY}
          familyMembers={FAMILY_MEMBERS} memberColors={MEMBER_COLORS}
          activeMember={activeMember} onMemberChange={setActiveMember}
        />;
      case 'onboarding':
        return <OnboardingScreen onBack={goBack} onComplete={() => { navigate('benefits', { replace: true }); }}/>;
      case 'settings':
        return <SettingsScreen
          onLogout={() => { setLoggedIn(false); setScreen('login'); }}
          onAddContract={() => navigate('onboarding')}
        />;
      default:
        return null;
    }
  };

  return (
    <ThemeCtx.Provider value={{ dark: darkMode, accent: accentColor }}>
      <div style={{
        height: '100%', display: 'flex', flexDirection: 'column',
        background: darkMode ? KC.color.darkBg : KC.color.bg,
        color: darkMode ? KC.color.darkText : KC.color.text,
      }}>
        <KCTopBar
          onBack={showBack ? goBack : undefined}
          title={backTitles[screen] || ''}
          onSettings={showShell ? () => handleTabChange('settings') : undefined}
        />
        {renderScreen()}
        {showShell && (
          <KCBottomNav
            activeTab={activeTab}
            onTabChange={handleTabChange}
            onUpload={() => navigate('upload')}
          />
        )}
      </div>
    </ThemeCtx.Provider>
  );
}

// ═══════════════════════════════════════════════════════════════
// TWEAKS
// ═══════════════════════════════════════════════════════════════

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "darkMode": false,
  "accentColor": "#0D9488",
  "startScreen": "home"
}/*EDITMODE-END*/;

function AppWithTweaks() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  KC.color.accent = t.accentColor;
  KC.color.accentHover = t.accentColor;

  return (
    <>
      <KaiserClaimApp
        key={t.startScreen + t.accentColor + t.darkMode}
        darkMode={t.darkMode}
        accentColor={t.accentColor}
      />
      <TweaksPanel>
        <TweakSection label="Darstellung"/>
        <TweakToggle label="Dark Mode" value={t.darkMode}
          onChange={v => setTweak('darkMode', v)}/>
        <TweakColor label="Akzentfarbe" value={t.accentColor}
          options={['#0D9488', '#2563EB', '#7C3AED', '#EA580C']}
          onChange={v => setTweak('accentColor', v)}/>
        <TweakSection label="Demo"/>
        <TweakSelect label="Startbildschirm" value={t.startScreen}
          options={['home', 'invoices', 'benefits', 'stats', 'settings', 'login']}
          onChange={v => setTweak('startScreen', v)}/>
      </TweaksPanel>
    </>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<AppWithTweaks/>);
