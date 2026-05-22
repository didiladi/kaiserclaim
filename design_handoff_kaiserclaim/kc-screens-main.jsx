// kc-screens-main.jsx — Login, Home/Dashboard, Upload screens

// ═══════════════════════════════════════════════════════════════
// LOGIN SCREEN
// ═══════════════════════════════════════════════════════════════

function LoginScreen({ onLogin }) {
  const { dark } = useTheme();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = () => {
    if (!email.includes('@')) { setError('Bitte gültige E-Mail-Adresse eingeben'); return; }
    setError(''); setLoading(true);
    setTimeout(() => { setLoading(false); onLogin(); }, 1200);
  };

  return (
    <div style={{
      minHeight: '100%', display: 'flex', flexDirection: 'column',
      justifyContent: 'center', padding: '40px 24px',
      background: dark ? KC.color.darkBg : KC.color.bg,
    }}>
      <div style={{ textAlign: 'center', marginBottom: 48 }}>
        <div style={{
          width: 64, height: 64, borderRadius: 20, margin: '0 auto 20px',
          background: KC.color.accent,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: `0 8px 24px ${KC.color.accent}33`,
        }}>
          <KCIcon name="shield" size={32} color="#fff"/>
        </div>
        <h1 style={{
          fontSize: 28, fontWeight: 700, margin: '0 0 8px',
          letterSpacing: '-0.02em',
          color: dark ? KC.color.darkText : KC.color.brand,
        }}>
          Kaiser<span style={{ fontWeight: 400 }}>Claim</span>
        </h1>
        <p style={{
          fontSize: 15, color: dark ? KC.color.darkTextSec : KC.color.textSec,
          margin: 0, lineHeight: 1.5,
        }}>
          Ihre Gesundheitskosten.<br/>Automatisch erstattet.
        </p>
      </div>

      <KCCard style={{ marginBottom: 16 }} padding={24}>
        <KCInput
          label="E-Mail-Adresse" value={email}
          onChange={v => { setEmail(v); setError(''); }}
          placeholder="name@beispiel.at" type="email" icon="mail"
          error={error} style={{ marginBottom: 20 }}
        />
        <KCButton fullWidth size="lg" loading={loading} onClick={handleSubmit}>
          Anmelden
        </KCButton>
      </KCCard>

      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
        marginTop: 24,
      }}>
        <KCIcon name="lock" size={14} color={dark ? KC.color.darkTextSec : KC.color.textTri}/>
        <span style={{ fontSize: 12, color: dark ? KC.color.darkTextSec : KC.color.textTri }}>
          Ende-zu-Ende verschlüsselt · DSGVO-konform
        </span>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// HOME / DASHBOARD SCREEN
// ═══════════════════════════════════════════════════════════════

function HomeScreen({ invoices, benefits, familyMembers, activeMember, onMemberChange,
  onInvoice, onUpload, onViewAll, onBenefits, onStats }) {
  const { dark } = useTheme();

  // Filter by member
  const filtered = activeMember === 'all' ? invoices : invoices.filter(i => i.memberId === activeMember);
  const inProgress = filtered.filter(i => i.status !== 'abgeschlossen');
  const completed = filtered.filter(i => i.status === 'abgeschlossen');

  // Financial totals
  const totalPaid = filtered.reduce((s, i) => s + i.amount, 0);
  const totalReimbursed = completed.reduce((s, i) => s + i.amount, 0) * 0.82; // simulate partial reimbursement
  const totalOutstanding = inProgress.reduce((s, i) => s + i.amount, 0);
  const netCost = totalPaid - totalReimbursed;

  const recent = filtered.slice(0, 4);

  // Benefits nearing limit
  const alerts = [];
  benefits.forEach(contract => {
    const members = activeMember === 'all'
      ? contract.members
      : contract.members.filter(m => m.memberId === activeMember);
    members.forEach(member => {
      member.benefits.forEach(b => {
        const pct = (b.used / b.limit) * 100;
        if (pct >= 75) alerts.push({ ...b, memberName: member.name, memberId: member.memberId, pct });
      });
    });
  });

  return (
    <KCPage>
      {/* Family filter */}
      <div style={{ paddingTop: 16, marginBottom: 16 }}>
        <KCFamilyFilter members={familyMembers} selected={activeMember} onChange={onMemberChange}/>
      </div>

      {/* Hero financial card */}
      <div style={{ padding: '0 20px' }}>
        <div style={{
          background: `linear-gradient(135deg, ${KC.color.brand} 0%, #2D3A5E 100%)`,
          borderRadius: KC.r.xl, padding: '24px 20px', marginBottom: 16,
          position: 'relative', overflow: 'hidden',
        }}>
          <div style={{ position: 'absolute', top: -30, right: -30, width: 120, height: 120, borderRadius: 60, background: 'rgba(255,255,255,0.05)' }}/>
          <div style={{ position: 'absolute', bottom: -20, right: 40, width: 80, height: 80, borderRadius: 40, background: 'rgba(255,255,255,0.03)' }}/>

          <div style={{ fontSize: 12, fontWeight: 500, color: 'rgba(255,255,255,0.6)', marginBottom: 4 }}>
            Gesamtausgaben 2026
            {activeMember !== 'all' && ` · ${familyMembers.find(m => m.id === activeMember)?.name}`}
          </div>
          <KCMoney amount={totalPaid} size="hero" color="#FFFFFF" animated/>

          {/* Finance breakdown */}
          <div style={{ display: 'flex', gap: 10, marginTop: 16, flexWrap: 'wrap' }}>
            <div style={{ padding: '8px 12px', borderRadius: KC.r.md, background: 'rgba(255,255,255,0.1)', flex: 1, minWidth: 90 }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#fff' }}>
                €&thinsp;{totalReimbursed.toLocaleString('de-AT', {minimumFractionDigits: 0, maximumFractionDigits: 0})}
              </div>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.6)', fontWeight: 500, marginTop: 1 }}>Erstattet</div>
            </div>
            <div style={{ padding: '8px 12px', borderRadius: KC.r.md, background: 'rgba(255,255,255,0.1)', flex: 1, minWidth: 90 }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#fff' }}>{inProgress.length}</div>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.6)', fontWeight: 500, marginTop: 1 }}>In Bearbeitung</div>
            </div>
            <div style={{ padding: '8px 12px', borderRadius: KC.r.md, background: 'rgba(255,255,255,0.1)', flex: 1, minWidth: 90 }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#fff' }}>
                €&thinsp;{netCost.toLocaleString('de-AT', {minimumFractionDigits: 0, maximumFractionDigits: 0})}
              </div>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.6)', fontWeight: 500, marginTop: 1 }}>Eigenanteil</div>
            </div>
          </div>
        </div>
      </div>

      {/* Upload CTA */}
      <div style={{ padding: '0 20px', marginBottom: 20 }}>
        <KCButton fullWidth size="lg" icon="upload" onClick={onUpload}>
          Beleg hochladen
        </KCButton>
      </div>

      {/* Benefit alerts */}
      {alerts.length > 0 && (
        <div style={{ padding: '0 20px', marginBottom: 16 }}>
          {alerts.slice(0, 2).map((a, i) => (
            <div key={i} onClick={onBenefits} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '10px 12px', borderRadius: KC.r.md, cursor: 'pointer',
              background: a.pct >= 100 ? KC.color.dangerBg : '#FFF7ED',
              marginBottom: i < Math.min(alerts.length, 2) - 1 ? 6 : 0,
            }}>
              <KCIcon name="alertCircle" size={16} color={a.pct >= 100 ? '#DC2626' : '#EA580C'}/>
              <div style={{ flex: 1, fontSize: 12, fontWeight: 500, color: dark ? KC.color.darkText : KC.color.text }}>
                <strong>{a.memberName}: {a.name}</strong> — {a.pct >= 100 ? 'Limit erreicht' : `${Math.round(a.pct)}% ausgeschöpft`}
              </div>
              <KCIcon name="chevronRight" size={14} color={dark ? KC.color.darkTextSec : KC.color.textTri}/>
            </div>
          ))}
        </div>
      )}

      {/* Quick stats link */}
      <div style={{ padding: '0 20px', marginBottom: 20 }}>
        <KCCard hover onClick={onStats} padding={14}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 38, height: 38, borderRadius: 10,
              background: dark ? KC.color.darkSurfaceAlt : KC.color.accentLight,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <KCIcon name="trending" size={18} color={KC.color.accent}/>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: dark ? KC.color.darkText : KC.color.text }}>
                Statistiken ansehen
              </div>
              <div style={{ fontSize: 12, color: dark ? KC.color.darkTextSec : KC.color.textTri }}>
                Monatliche Ausgaben & Erstattungen
              </div>
            </div>
            <KCIcon name="chevronRight" size={18} color={dark ? KC.color.darkTextSec : KC.color.textTri}/>
          </div>
        </KCCard>
      </div>

      {/* Recent invoices */}
      <KCSection title="Letzte Belege" action="Alle anzeigen" onAction={onViewAll}/>
      <div style={{ padding: '0 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {recent.length === 0 ? (
          <KCEmptyState icon="receipt" title="Keine Belege"
            message="Laden Sie Ihren ersten Beleg hoch."/>
        ) : recent.map(inv => {
          const memberColor = MEMBER_COLORS[inv.memberId] || KC.color.textTri;
          return (
            <KCCard key={inv.id} hover onClick={() => onInvoice(inv.id)} padding={14}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <KCAvatar
                  initials={familyMembers.find(m => m.id === inv.memberId)?.initials || '?'}
                  color={memberColor} size={38}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 14, fontWeight: 600, marginBottom: 3,
                    color: dark ? KC.color.darkText : KC.color.text,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>{inv.provider}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <KCStatusPill status={inv.status}/>
                    <span style={{ fontSize: 11, color: dark ? KC.color.darkTextSec : KC.color.textTri }}>{inv.relativeTime}</span>
                  </div>
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <KCMoney amount={inv.amount} size="sm"/>
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
// UPLOAD SCREEN
// ═══════════════════════════════════════════════════════════════

function UploadScreen({ onBack, onSuccess, familyMembers }) {
  const { dark } = useTheme();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [contract, setContract] = useState('');
  const [category, setCategory] = useState('');
  const [member, setMember] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleFile = (f) => {
    setFile(f); setError('');
    if (f.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (e) => setPreview(e.target.result);
      reader.readAsDataURL(f);
    } else { setPreview(null); }
  };
  const clearFile = () => { setFile(null); setPreview(null); };

  const handleUpload = () => {
    if (!file) { setError('Bitte wählen Sie einen Beleg aus.'); return; }
    setError(''); setUploading(true);
    setTimeout(() => { setUploading(false); setSuccess(true); setTimeout(() => onSuccess(), 1500); }, 2000);
  };

  if (success) {
    return (
      <div style={{
        minHeight: '100%', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', padding: 40,
        background: dark ? KC.color.darkBg : KC.color.bg,
      }}>
        <div style={{
          width: 72, height: 72, borderRadius: 36, marginBottom: 20,
          background: '#DCFCE7', display: 'flex', alignItems: 'center', justifyContent: 'center',
          animation: 'kcPop 0.4s ease',
        }}>
          <KCIcon name="checkCircle" size={36} color="#16A34A"/>
        </div>
        <div style={{ fontSize: 20, fontWeight: 700, color: dark ? KC.color.darkText : KC.color.text, marginBottom: 6 }}>
          Beleg hochgeladen
        </div>
        <div style={{ fontSize: 14, color: dark ? KC.color.darkTextSec : KC.color.textSec, textAlign: 'center' }}>
          Ihr Beleg wird jetzt verarbeitet.
        </div>
      </div>
    );
  }

  const memberOptions = (familyMembers || []).map(m => ({ value: m.id, label: m.name + ' Kaiser' }));

  return (
    <KCPage>
      <div style={{ padding: '20px 20px 0' }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: '0 0 4px', color: dark ? KC.color.darkText : KC.color.text }}>
          Beleg hochladen
        </h1>
        <p style={{ fontSize: 14, color: dark ? KC.color.darkTextSec : KC.color.textSec, margin: '0 0 24px' }}>
          Fotografieren Sie Ihren Beleg oder wählen Sie eine Datei.
        </p>

        <KCDropZone onFile={handleFile} preview={preview} onClear={clearFile}/>

        {file && !file.type.startsWith('image/') && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '12px 14px', borderRadius: KC.r.md, marginTop: 12,
            background: dark ? KC.color.darkSurface : KC.color.surface,
            border: `1px solid ${dark ? KC.color.darkBorder : KC.color.border}`,
          }}>
            <KCIcon name="file" size={20} color={KC.color.accent}/>
            <span style={{ flex: 1, fontSize: 14, color: dark ? KC.color.darkText : KC.color.text,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{file.name}</span>
            <button onClick={clearFile} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2 }}>
              <KCIcon name="x" size={16} color={dark ? KC.color.darkTextSec : KC.color.textTri}/>
            </button>
          </div>
        )}

        <div style={{ marginTop: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <KCSelect label="Familienmitglied" value={member} onChange={setMember}
            placeholder="Person wählen (optional)" options={memberOptions}/>
          <KCSelect label="Vertrag" value={contract} onChange={setContract}
            placeholder="Vertrag wählen (optional)"
            options={[
              { value: 'merkur', label: 'Merkur Sonderklasse — MS-2024-78912' },
              { value: 'oegk', label: 'ÖGK — Pflichtversicherung' },
            ]}/>
          <KCSelect label="Leistung" value={category} onChange={setCategory}
            placeholder="Kategorie wählen (optional)"
            options={[
              { value: 'zahnarzt', label: 'Zahnreinigung (Limit: € 150)' },
              { value: 'physio', label: 'Physiotherapie (Limit: € 800)' },
              { value: 'allgemein', label: 'Allgemeinmedizin (Limit: € 1.200)' },
              { value: 'medikamente', label: 'Medikamente (Limit: € 500)' },
              { value: 'sehbehelfe', label: 'Sehbehelfe (Limit: € 200)' },
              { value: 'kinderarzt', label: 'Kinderarzt (Limit: € 400)' },
            ]}/>
        </div>

        {error && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 14px', borderRadius: KC.r.md, marginTop: 16,
            background: KC.color.dangerBg, color: KC.color.danger, fontSize: 13, fontWeight: 500,
          }}>
            <KCIcon name="alertCircle" size={16} color={KC.color.danger}/>{error}
          </div>
        )}

        <div style={{ marginTop: 24, paddingBottom: 20 }}>
          <KCButton fullWidth size="lg" loading={uploading} onClick={handleUpload}>
            Beleg hochladen
          </KCButton>
        </div>
      </div>
    </KCPage>
  );
}

Object.assign(window, { LoginScreen, HomeScreen, UploadScreen });
