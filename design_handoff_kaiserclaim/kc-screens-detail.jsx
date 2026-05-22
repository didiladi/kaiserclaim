// kc-screens-detail.jsx — Invoice List, Invoice Detail, Benefits, Onboarding, Settings

// ═══════════════════════════════════════════════════════════════
// INVOICE LIST SCREEN
// ═══════════════════════════════════════════════════════════════

function InvoiceListScreen({ invoices, familyMembers, activeMember, onMemberChange, onInvoice }) {
  const { dark } = useTheme();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');

  const filterTabs = [
    { id: 'all', label: 'Alle' },
    { id: 'in_progress', label: 'Laufend' },
    { id: 'abgeschlossen', label: 'Fertig' },
  ];

  const displayedInvoices = invoices.filter(inv => {
    if (activeMember !== 'all' && inv.memberId !== activeMember) return false;
    if (filter === 'in_progress' && inv.status === 'abgeschlossen') return false;
    if (filter === 'abgeschlossen' && inv.status !== 'abgeschlossen') return false;
    if (search && !inv.provider.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <KCPage>
      <div style={{ padding: '16px 0 0' }}>
        {/* Family filter */}
        <KCFamilyFilter members={familyMembers} selected={activeMember} onChange={onMemberChange}
          style={{ marginBottom: 16 }}/>

        <div style={{ padding: '0 20px' }}>
          <h1 style={{ fontSize: 22, fontWeight: 700, margin: '0 0 14px', color: dark ? KC.color.darkText : KC.color.text }}>
            Belege
            {activeMember !== 'all' && (
              <span style={{ fontSize: 14, fontWeight: 500, color: dark ? KC.color.darkTextSec : KC.color.textSec, marginLeft: 8 }}>
                {familyMembers.find(m => m.id === activeMember)?.name}
              </span>
            )}
          </h1>

          {/* Search */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            height: 44, padding: '0 14px', marginBottom: 12,
            background: dark ? KC.color.darkSurfaceAlt : KC.color.surfaceAlt,
            borderRadius: KC.r.md,
          }}>
            <KCIcon name="search" size={18} color={dark ? KC.color.darkTextSec : KC.color.textTri}/>
            <input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Belege durchsuchen..."
              style={{
                flex: 1, border: 'none', background: 'none', outline: 'none',
                fontSize: 14, fontFamily: 'inherit',
                color: dark ? KC.color.darkText : KC.color.text,
              }}/>
          </div>

          {/* Filter tabs */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
            {filterTabs.map(tab => (
              <button key={tab.id} onClick={() => setFilter(tab.id)} style={{
                padding: '6px 14px', borderRadius: KC.r.pill,
                background: filter === tab.id ? KC.color.brand : (dark ? KC.color.darkSurfaceAlt : KC.color.surfaceAlt),
                color: filter === tab.id ? '#fff' : (dark ? KC.color.darkTextSec : KC.color.textSec),
                border: 'none', fontSize: 13, fontWeight: 600,
                cursor: 'pointer', fontFamily: 'inherit', transition: 'all 0.2s',
              }}>{tab.label}</button>
            ))}
          </div>
        </div>
      </div>

      {/* Invoice list */}
      <div style={{ padding: '0 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {displayedInvoices.length === 0 ? (
          <KCEmptyState icon="receipt" title="Keine Belege gefunden"
            message={search ? 'Versuchen Sie einen anderen Suchbegriff.' : 'Laden Sie Ihren ersten Beleg hoch.'}/>
        ) : displayedInvoices.map(inv => {
          const mem = familyMembers.find(m => m.id === inv.memberId);
          return (
            <KCCard key={inv.id} hover onClick={() => onInvoice(inv.id)} padding={14}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <KCAvatar initials={mem?.initials || '?'} color={mem?.color || '#999'} size={38}/>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
                    <div>
                      <div style={{
                        fontSize: 14, fontWeight: 600, color: dark ? KC.color.darkText : KC.color.text,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 200,
                      }}>{inv.provider}</div>
                      <div style={{ fontSize: 11, color: dark ? KC.color.darkTextSec : KC.color.textTri, marginTop: 1 }}>
                        {inv.patient} · {inv.date}
                      </div>
                    </div>
                    <KCMoney amount={inv.amount} size="sm"/>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <KCStatusPill status={inv.status}/>
                    <span style={{ fontSize: 11, color: dark ? KC.color.darkTextSec : KC.color.textTri }}>{inv.relativeTime}</span>
                  </div>
                </div>
              </div>
            </KCCard>
          );
        })}
      </div>
    </KCPage>
  );
}

// ═══════════════════════════════════════════════════════════════
// INVOICE DETAIL SCREEN
// ═══════════════════════════════════════════════════════════════

function InvoiceDetailScreen({ invoice, onBack }) {
  const { dark } = useTheme();
  if (!invoice) return null;

  const pipeline = invoice.pipeline === 'pharmacy' ? PIPELINE_PHARMACY : PIPELINE_STANDARD;
  const currentStep = invoice.currentStep;

  const timestamps = {};
  const baseDate = new Date(2026, 4, parseInt(invoice.date.split('.')[0]));
  pipeline.forEach((step, i) => {
    if (i <= currentStep) {
      const d = new Date(baseDate);
      d.setHours(d.getHours() + i * 8 + Math.floor(Math.random() * 4));
      timestamps[step] = `${d.getDate().toString().padStart(2,'0')}.${(d.getMonth()+1).toString().padStart(2,'0')}.${d.getFullYear()}, ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`;
    }
  });

  const showMerkurAction = invoice.status === 'von_oegk' || invoice.status === 'bereit_merkur';

  const infoRows = [
    { label: 'Betrag', value: <KCMoney amount={invoice.amount} size="md"/> },
    { label: 'Datum', value: invoice.date },
    { label: 'Anbieter', value: invoice.provider },
    { label: 'Patient', value: invoice.patient },
    { label: 'Kategorie', value: invoice.category },
    { label: 'Vertrag', value: invoice.contract },
    { label: 'Hochgeladen am', value: invoice.uploaded },
  ];

  return (
    <KCPage>
      <div style={{ padding: '20px 20px 0' }}>
        <KCCard padding={0} style={{ marginBottom: 20, overflow: 'hidden' }}>
          <div style={{
            padding: '14px 18px',
            background: dark ? KC.color.darkSurfaceAlt : KC.color.surfaceAlt,
            borderBottom: `1px solid ${dark ? KC.color.darkBorder : KC.color.borderLight}`,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <span style={{ fontSize: 15, fontWeight: 700, color: dark ? KC.color.darkText : KC.color.text }}>
              Belegdetails
            </span>
            <KCStatusPill status={invoice.status} size="md"/>
          </div>
          <div style={{ padding: '4px 18px 14px' }}>
            {infoRows.map((row, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px 0',
                borderBottom: i < infoRows.length - 1 ? `1px solid ${dark ? KC.color.darkBorder : KC.color.borderLight}` : 'none',
              }}>
                <span style={{ fontSize: 13, color: dark ? KC.color.darkTextSec : KC.color.textSec, fontWeight: 500 }}>
                  {row.label}
                </span>
                <span style={{ fontSize: 14, fontWeight: 500, color: dark ? KC.color.darkText : KC.color.text }}>
                  {row.value}
                </span>
              </div>
            ))}
          </div>
        </KCCard>

        {showMerkurAction && (
          <KCButton fullWidth size="lg" icon="send" style={{ marginBottom: 20 }}
            onClick={() => alert('Demo: An Merkur übermittelt')}>
            An Merkur übermitteln
          </KCButton>
        )}

        <KCCard padding={20} style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 16, color: dark ? KC.color.darkText : KC.color.text }}>
            Erstattungs-Pipeline
            <span style={{ fontSize: 11, fontWeight: 500, marginLeft: 8, color: dark ? KC.color.darkTextSec : KC.color.textTri }}>
              {invoice.pipeline === 'pharmacy' ? 'Apotheke (Kurzweg)' : 'Standardweg'}
            </span>
          </div>
          <KCStepper steps={pipeline} currentStep={currentStep} timestamps={timestamps}/>
        </KCCard>
      </div>
    </KCPage>
  );
}

// ═══════════════════════════════════════════════════════════════
// BENEFITS DASHBOARD (per-member)
// ═══════════════════════════════════════════════════════════════

function BenefitsScreen({ benefits, familyMembers, activeMember, onMemberChange, onAddContract }) {
  const { dark } = useTheme();
  return (
    <KCPage>
      <div style={{ padding: '16px 0 0' }}>
        <KCFamilyFilter members={familyMembers} selected={activeMember} onChange={onMemberChange}
          style={{ marginBottom: 16 }}/>

        <div style={{ padding: '0 20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
            <div>
              <h1 style={{ fontSize: 22, fontWeight: 700, margin: '0 0 4px', color: dark ? KC.color.darkText : KC.color.text }}>
                Leistungen
              </h1>
              <p style={{ fontSize: 14, color: dark ? KC.color.darkTextSec : KC.color.textSec, margin: 0 }}>
                {activeMember === 'all' ? 'Alle Familienmitglieder' : familyMembers.find(m => m.id === activeMember)?.name + ' Kaiser'}
              </p>
            </div>
            <KCButton variant="secondary" size="sm" icon="plus" onClick={onAddContract}>Vertrag</KCButton>
          </div>
        </div>

        {benefits.map((contract, ci) => {
          const visibleMembers = activeMember === 'all'
            ? contract.members
            : contract.members.filter(m => m.memberId === activeMember);

          return (
            <div key={ci} style={{ padding: '0 20px', marginBottom: 24 }}>
              {/* Contract header */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '12px 16px', borderRadius: `${KC.r.lg}px ${KC.r.lg}px 0 0`,
                background: dark ? KC.color.darkSurface : KC.color.surface,
                border: `1px solid ${dark ? KC.color.darkBorder : KC.color.border}`, borderBottom: 'none',
              }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 10,
                  background: dark ? KC.color.darkSurfaceAlt : KC.color.accentLight,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <KCIcon name="shield" size={18} color={KC.color.accent}/>
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: dark ? KC.color.darkText : KC.color.text }}>
                    {contract.contract}
                  </div>
                  <div style={{ fontSize: 12, color: dark ? KC.color.darkTextSec : KC.color.textTri }}>
                    {contract.policyNumber}
                  </div>
                </div>
              </div>

              {/* Members & benefits */}
              <div style={{
                background: dark ? KC.color.darkSurface : KC.color.surface,
                border: `1px solid ${dark ? KC.color.darkBorder : KC.color.border}`,
                borderRadius: `0 0 ${KC.r.lg}px ${KC.r.lg}px`,
                overflow: 'hidden',
              }}>
                {visibleMembers.map((member, mi) => {
                  const mem = familyMembers.find(m => m.id === member.memberId);
                  return (
                    <div key={mi}>
                      {/* Member header */}
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '12px 16px',
                        background: dark ? KC.color.darkSurfaceAlt : KC.color.surfaceAlt,
                        borderBottom: `1px solid ${dark ? KC.color.darkBorder : KC.color.borderLight}`,
                        borderTop: mi > 0 ? `1px solid ${dark ? KC.color.darkBorder : KC.color.border}` : 'none',
                      }}>
                        <KCAvatar initials={mem?.initials || '?'} color={mem?.color || '#999'} size={28}/>
                        <span style={{ fontSize: 13, fontWeight: 600, color: dark ? KC.color.darkText : KC.color.text }}>
                          {member.name}
                        </span>
                      </div>

                      {/* Benefits */}
                      {member.benefits.map((b, bi) => (
                        <div key={bi} style={{
                          padding: '14px 16px',
                          borderBottom: bi < member.benefits.length - 1
                            ? `1px solid ${dark ? KC.color.darkBorder : KC.color.borderLight}` : 'none',
                        }}>
                          <div style={{
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8,
                          }}>
                            <span style={{ fontSize: 14, fontWeight: 600, color: dark ? KC.color.darkText : KC.color.text }}>
                              {b.name}
                            </span>
                            <span style={{
                              fontSize: 11, fontWeight: 500, padding: '2px 8px',
                              borderRadius: KC.r.pill,
                              background: dark ? KC.color.darkSurfaceAlt : KC.color.surfaceAlt,
                              color: dark ? KC.color.darkTextSec : KC.color.textTri,
                            }}>{b.period}</span>
                          </div>
                          <KCProgressBar used={b.used} limit={b.limit} height={6}/>
                        </div>
                      ))}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </KCPage>
  );
}

// ═══════════════════════════════════════════════════════════════
// ONBOARDING / ADD CONTRACT FLOW
// ═══════════════════════════════════════════════════════════════

function OnboardingScreen({ onBack, onComplete }) {
  const { dark } = useTheme();
  const [step, setStep] = useState(0);
  const [provider, setProvider] = useState('');
  const [policyNumber, setPolicyNumber] = useState('');
  const [file, setFile] = useState(null);
  const [parsing, setParsing] = useState(false);
  const [parsed, setParsed] = useState(false);

  const extractedBenefits = [
    { name: 'Zahnbehandlung', limit: 200, period: 'jährlich' },
    { name: 'Physiotherapie', limit: 1000, period: 'jährlich' },
    { name: 'Allgemeinmedizin', limit: 1500, period: 'jährlich' },
    { name: 'Medikamente', limit: 600, period: 'jährlich' },
    { name: 'Sehbehelfe', limit: 300, period: '2-jährlich' },
  ];

  const handleParse = () => {
    setParsing(true);
    setTimeout(() => { setParsing(false); setParsed(true); setStep(2); }, 2500);
  };

  const stepLabels = ['Daten', 'Dokument', 'Bestätigen'];

  const steps = [
    <div key={0}>
      <h2 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 6px', color: dark ? KC.color.darkText : KC.color.text }}>
        Vertrag hinzufügen
      </h2>
      <p style={{ fontSize: 14, color: dark ? KC.color.darkTextSec : KC.color.textSec, margin: '0 0 24px' }}>
        Geben Sie die Daten Ihrer Privatversicherung ein.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <KCSelect label="Versicherer" value={provider} onChange={setProvider}
          placeholder="Versicherer wählen"
          options={[
            { value: 'merkur', label: 'Merkur Versicherung' },
            { value: 'uniqa', label: 'UNIQA' },
            { value: 'generali', label: 'Generali' },
            { value: 'wiener', label: 'Wiener Städtische' },
            { value: 'allianz', label: 'Allianz' },
          ]}/>
        <KCInput label="Polizzennummer" value={policyNumber} onChange={setPolicyNumber}
          placeholder="z. B. MS-2024-78912" icon="creditCard"/>
      </div>
      <KCButton fullWidth size="lg" style={{ marginTop: 28 }}
        disabled={!provider || !policyNumber} onClick={() => setStep(1)}>
        Weiter
      </KCButton>
    </div>,

    <div key={1}>
      <h2 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 6px', color: dark ? KC.color.darkText : KC.color.text }}>
        Vertragsdokument
      </h2>
      <p style={{ fontSize: 14, color: dark ? KC.color.darkTextSec : KC.color.textSec, margin: '0 0 24px' }}>
        Laden Sie Ihr Versicherungsdokument hoch. Wir extrahieren die Leistungen automatisch.
      </p>
      <KCDropZone onFile={(f) => setFile(f)} preview={null} onClear={() => setFile(null)}/>
      {file && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '12px 14px', borderRadius: KC.r.md, marginTop: 12,
          background: dark ? KC.color.darkSurface : KC.color.surface,
          border: `1px solid ${dark ? KC.color.darkBorder : KC.color.border}`,
        }}>
          <KCIcon name="file" size={20} color={KC.color.accent}/>
          <span style={{ flex: 1, fontSize: 14, color: dark ? KC.color.darkText : KC.color.text }}>
            {file.name || 'Vertragsdokument.pdf'}
          </span>
          <KCIcon name="checkCircle" size={18} color="#16A34A"/>
        </div>
      )}
      {parsing && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '32px 0', gap: 16 }}>
          <div style={{ animation: 'kcSpin 1s linear infinite', display: 'flex' }}>
            <KCIcon name="loader" size={32} color={KC.color.accent}/>
          </div>
          <div style={{ fontSize: 14, fontWeight: 500, color: dark ? KC.color.darkTextSec : KC.color.textSec }}>
            Vertrag wird analysiert...
          </div>
          <div style={{
            width: '80%', height: 4, borderRadius: 2, overflow: 'hidden',
            background: dark ? KC.color.darkSurfaceAlt : KC.color.surfaceAlt,
          }}>
            <div style={{ width: '70%', height: '100%', borderRadius: 2, background: KC.color.accent, animation: 'kcProgress 2.5s ease forwards' }}/>
          </div>
        </div>
      )}
      {!parsing && (
        <KCButton fullWidth size="lg" style={{ marginTop: 24 }}
          disabled={!file} onClick={handleParse}>
          Vertrag analysieren
        </KCButton>
      )}
    </div>,

    <div key={2}>
      <div style={{
        width: 56, height: 56, borderRadius: 16, marginBottom: 16,
        background: '#DCFCE7', display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <KCIcon name="checkCircle" size={28} color="#16A34A"/>
      </div>
      <h2 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 6px', color: dark ? KC.color.darkText : KC.color.text }}>
        Leistungen erkannt
      </h2>
      <p style={{ fontSize: 14, color: dark ? KC.color.darkTextSec : KC.color.textSec, margin: '0 0 20px' }}>
        Bitte bestätigen Sie die erkannten Leistungen Ihres Vertrags.
      </p>
      <KCCard padding={0} style={{ marginBottom: 24, overflow: 'hidden' }}>
        {extractedBenefits.map((b, i) => (
          <div key={i} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '14px 16px',
            borderBottom: i < extractedBenefits.length - 1 ? `1px solid ${dark ? KC.color.darkBorder : KC.color.borderLight}` : 'none',
          }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: dark ? KC.color.darkText : KC.color.text }}>{b.name}</div>
              <div style={{ fontSize: 12, color: dark ? KC.color.darkTextSec : KC.color.textTri, marginTop: 2 }}>{b.period}</div>
            </div>
            <div style={{ fontSize: 15, fontWeight: 600, color: dark ? KC.color.darkText : KC.color.text }}>
              €&thinsp;{b.limit.toLocaleString('de-AT')}
            </div>
          </div>
        ))}
      </KCCard>
      <KCButton fullWidth size="lg" onClick={onComplete}>Vertrag speichern</KCButton>
    </div>,
  ];

  return (
    <KCPage>
      <div style={{ padding: '20px 20px 0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 28 }}>
          {stepLabels.map((label, i) => (
            <React.Fragment key={i}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{
                  width: 24, height: 24, borderRadius: 12,
                  background: i <= step ? KC.color.accent : (dark ? KC.color.darkSurfaceAlt : KC.color.surfaceAlt),
                  color: i <= step ? '#fff' : (dark ? KC.color.darkTextSec : KC.color.textTri),
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 700, transition: 'all 0.3s',
                }}>
                  {i < step ? <KCIcon name="check" size={12} color="#fff"/> : i + 1}
                </div>
                <span style={{
                  fontSize: 12, fontWeight: i === step ? 600 : 400,
                  color: i <= step ? (dark ? KC.color.darkText : KC.color.text) : (dark ? KC.color.darkTextSec : KC.color.textTri),
                }}>{label}</span>
              </div>
              {i < 2 && <div style={{
                flex: 1, height: 1,
                background: i < step ? KC.color.accent : (dark ? KC.color.darkBorder : KC.color.border),
                transition: 'background 0.3s',
              }}/>}
            </React.Fragment>
          ))}
        </div>
        {steps[step]}
      </div>
    </KCPage>
  );
}

// ═══════════════════════════════════════════════════════════════
// SETTINGS SCREEN
// ═══════════════════════════════════════════════════════════════

function SettingsScreen({ onLogout, onAddContract }) {
  const { dark } = useTheme();

  const Section = ({ title, children }) => (
    <div style={{ marginBottom: 24 }}>
      <div style={{
        fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em',
        color: dark ? KC.color.darkTextSec : KC.color.textTri, padding: '0 4px', marginBottom: 8,
      }}>{title}</div>
      <KCCard padding={0} style={{ overflow: 'hidden' }}>{children}</KCCard>
    </div>
  );

  const Row = ({ icon, label, value, danger, onClick, trailing }) => (
    <button onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 12, width: '100%',
      padding: '14px 16px', background: 'none', border: 'none',
      borderBottom: `1px solid ${dark ? KC.color.darkBorder : KC.color.borderLight}`,
      cursor: onClick ? 'pointer' : 'default', fontFamily: 'inherit', textAlign: 'left',
    }}>
      <KCIcon name={icon} size={20}
        color={danger ? KC.color.danger : (dark ? KC.color.darkTextSec : KC.color.textSec)}/>
      <span style={{
        flex: 1, fontSize: 14, fontWeight: 500,
        color: danger ? KC.color.danger : (dark ? KC.color.darkText : KC.color.text),
      }}>{label}</span>
      {value && <span style={{ fontSize: 13, color: dark ? KC.color.darkTextSec : KC.color.textTri }}>{value}</span>}
      {trailing || (onClick && <KCIcon name="chevronRight" size={16} color={dark ? KC.color.darkTextSec : KC.color.textTri}/>)}
    </button>
  );

  return (
    <KCPage>
      <div style={{ padding: '20px 20px 0' }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: '0 0 20px', color: dark ? KC.color.darkText : KC.color.text }}>
          Einstellungen
        </h1>

        <Section title="Konto">
          <Row icon="user" label="Profil" value="Maria Kaiser"/>
          <Row icon="mail" label="E-Mail" value="maria@kaiser.at"/>
          <div style={{ borderBottom: 'none' }}>
            <Row icon="globe" label="Sprache" value="Deutsch (AT)"/>
          </div>
        </Section>

        <Section title="Versicherungsportal">
          <div style={{
            padding: '14px 16px',
            borderBottom: `1px solid ${dark ? KC.color.darkBorder : KC.color.borderLight}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <div style={{
                width: 32, height: 32, borderRadius: 8,
                background: dark ? '#1a2e1a' : '#F0FDF4',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <KCIcon name="shield" size={16} color="#16A34A"/>
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: dark ? KC.color.darkText : KC.color.text }}>
                  Sicherer Tresor
                </div>
                <div style={{ fontSize: 11, color: dark ? KC.color.darkTextSec : KC.color.textTri }}>
                  AES-256 verschlüsselt · Nur auf Ihrem Gerät
                </div>
              </div>
            </div>
          </div>
          <Row icon="lock" label="ÖGK-Portal" value="Hinterlegt" onClick={() => {}}
            trailing={<div style={{ width: 8, height: 8, borderRadius: 4, background: '#16A34A' }}/>}/>
          <div style={{ borderBottom: 'none' }}>
            <Row icon="lock" label="Merkur-Portal" value="Hinterlegt" onClick={() => {}}
              trailing={<div style={{ width: 8, height: 8, borderRadius: 4, background: '#16A34A' }}/>}/>
          </div>
        </Section>

        <Section title="Verträge">
          <Row icon="creditCard" label="Merkur Sonderklasse" value="MS-2024-78912" onClick={() => {}}/>
          <div style={{ borderBottom: 'none' }}>
            <Row icon="plus" label="Vertrag hinzufügen" onClick={onAddContract}/>
          </div>
        </Section>

        <Section title="Sonstiges">
          <div style={{ borderBottom: 'none' }}>
            <Row icon="logout" label="Abmelden" danger onClick={onLogout}/>
          </div>
        </Section>
      </div>
    </KCPage>
  );
}

Object.assign(window, {
  InvoiceListScreen, InvoiceDetailScreen, BenefitsScreen,
  OnboardingScreen, SettingsScreen,
});
