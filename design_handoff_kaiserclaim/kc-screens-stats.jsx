// kc-screens-stats.jsx — Statistics / Analytics screen

function StatsScreen({ invoices, monthly, yearly, familyMembers, memberColors, activeMember, onMemberChange }) {
  const { dark } = useTheme();
  const [view, setView] = useState('monthly'); // monthly | yearly | members

  // Filter invoices by member
  const filtered = activeMember === 'all' ? invoices : invoices.filter(i => i.memberId === activeMember);
  const totalPaid = filtered.reduce((s, i) => s + i.amount, 0);
  const totalCompleted = filtered.filter(i => i.status === 'abgeschlossen');
  const totalReimbursed = totalCompleted.reduce((s, i) => s + i.amount, 0) * 0.82;
  const eigenanteil = totalPaid - totalReimbursed;
  const reimbursementRate = totalPaid > 0 ? Math.round((totalReimbursed / totalPaid) * 100) : 0;

  // Per-member totals
  const memberTotals = familyMembers.filter(m => m.id !== 'all').map(m => {
    const memberInv = invoices.filter(i => i.memberId === m.id);
    const paid = memberInv.reduce((s, i) => s + i.amount, 0);
    const completed = memberInv.filter(i => i.status === 'abgeschlossen');
    const reimbursed = completed.reduce((s, i) => s + i.amount, 0) * 0.82;
    return { ...m, paid, reimbursed, count: memberInv.length, eigenanteil: paid - reimbursed };
  });

  // Monthly chart data
  const monthlyChart = monthly.map(m => {
    if (activeMember === 'all') {
      return {
        label: m.month,
        total: m.total,
        segments: Object.entries(m.members).map(([id, value]) => ({ memberId: id, value })),
      };
    } else {
      return {
        label: m.month,
        total: m.members[activeMember] || 0,
        value: m.members[activeMember] || 0,
        color: memberColors[activeMember] || KC.color.accent,
      };
    }
  });

  // Yearly chart data
  const yearlyChart = yearly.map(y => ({
    label: y.year,
    total: y.paid,
    value: y.paid,
    color: KC.color.accent,
  }));

  // Category breakdown
  const categoryTotals = {};
  filtered.forEach(inv => {
    if (!categoryTotals[inv.category]) categoryTotals[inv.category] = 0;
    categoryTotals[inv.category] += inv.amount;
  });
  const categories = Object.entries(categoryTotals)
    .sort((a, b) => b[1] - a[1])
    .map(([name, amount]) => ({ name, amount }));

  const viewTabs = [
    { id: 'monthly', label: 'Monatlich' },
    { id: 'yearly', label: 'Jährlich' },
    { id: 'members', label: 'Mitglieder' },
  ];

  return (
    <KCPage>
      <div style={{ padding: '16px 0 0' }}>
        <KCFamilyFilter members={familyMembers} selected={activeMember} onChange={onMemberChange}
          style={{ marginBottom: 16 }}/>

        <div style={{ padding: '0 20px' }}>
          <h1 style={{ fontSize: 22, fontWeight: 700, margin: '0 0 16px', color: dark ? KC.color.darkText : KC.color.text }}>
            Statistiken
            <span style={{ fontSize: 14, fontWeight: 400, color: dark ? KC.color.darkTextSec : KC.color.textSec, marginLeft: 8 }}>
              2026
            </span>
          </h1>

          {/* Summary cards */}
          <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
            <KCStatCard label="Ausgaben">
              €&thinsp;{totalPaid.toLocaleString('de-AT', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </KCStatCard>
            <KCStatCard label="Erstattet" color="#16A34A">
              €&thinsp;{totalReimbursed.toLocaleString('de-AT', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </KCStatCard>
          </div>
          <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
            <KCStatCard label="Eigenanteil" color="#EA580C">
              €&thinsp;{eigenanteil.toLocaleString('de-AT', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </KCStatCard>
            <KCStatCard label="Erstattungsquote" color={KC.color.accent}>
              {reimbursementRate}%
            </KCStatCard>
          </div>

          {/* View tabs */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
            {viewTabs.map(tab => (
              <button key={tab.id} onClick={() => setView(tab.id)} style={{
                padding: '6px 14px', borderRadius: KC.r.pill,
                background: view === tab.id ? KC.color.brand : (dark ? KC.color.darkSurfaceAlt : KC.color.surfaceAlt),
                color: view === tab.id ? '#fff' : (dark ? KC.color.darkTextSec : KC.color.textSec),
                border: 'none', fontSize: 13, fontWeight: 600,
                cursor: 'pointer', fontFamily: 'inherit', transition: 'all 0.2s',
              }}>{tab.label}</button>
            ))}
          </div>
        </div>

        {/* Monthly view */}
        {view === 'monthly' && (
          <div style={{ padding: '0 20px' }}>
            <KCCard padding={20} style={{ marginBottom: 20 }}>
              <div style={{
                fontSize: 14, fontWeight: 600, marginBottom: 16,
                color: dark ? KC.color.darkText : KC.color.text,
              }}>
                Monatliche Ausgaben
              </div>
              <KCBarChart data={monthlyChart} height={160} memberColors={memberColors}
                showLegend={activeMember === 'all'}/>
            </KCCard>

            {/* Monthly breakdown table */}
            <KCCard padding={0} style={{ overflow: 'hidden', marginBottom: 20 }}>
              <div style={{
                padding: '12px 16px',
                background: dark ? KC.color.darkSurfaceAlt : KC.color.surfaceAlt,
                borderBottom: `1px solid ${dark ? KC.color.darkBorder : KC.color.borderLight}`,
                fontSize: 13, fontWeight: 600, color: dark ? KC.color.darkText : KC.color.text,
              }}>
                Aufschlüsselung
              </div>
              {monthly.map((m, i) => {
                const amount = activeMember === 'all' ? m.total : (m.members[activeMember] || 0);
                return (
                  <div key={i} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '12px 16px',
                    borderBottom: i < monthly.length - 1 ? `1px solid ${dark ? KC.color.darkBorder : KC.color.borderLight}` : 'none',
                  }}>
                    <span style={{ fontSize: 14, fontWeight: 500, color: dark ? KC.color.darkText : KC.color.text }}>
                      {m.month} 2026
                    </span>
                    <span style={{
                      fontSize: 14, fontWeight: 600,
                      fontVariantNumeric: 'tabular-nums',
                      color: dark ? KC.color.darkText : KC.color.text,
                    }}>
                      €&thinsp;{amount.toLocaleString('de-AT', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                );
              })}
            </KCCard>
          </div>
        )}

        {/* Yearly view */}
        {view === 'yearly' && (
          <div style={{ padding: '0 20px' }}>
            <KCCard padding={20} style={{ marginBottom: 20 }}>
              <div style={{
                fontSize: 14, fontWeight: 600, marginBottom: 16,
                color: dark ? KC.color.darkText : KC.color.text,
              }}>
                Jahresvergleich
              </div>
              <KCBarChart data={yearlyChart} height={140}/>
            </KCCard>

            {/* Yearly detail cards */}
            {yearly.map((y, i) => (
              <KCCard key={i} padding={16} style={{ marginBottom: 10 }}>
                <div style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10,
                }}>
                  <span style={{ fontSize: 16, fontWeight: 700, color: dark ? KC.color.darkText : KC.color.text }}>
                    {y.year}
                  </span>
                  {y.year === '2026' && (
                    <span style={{
                      fontSize: 11, fontWeight: 500, padding: '2px 8px', borderRadius: KC.r.pill,
                      background: KC.color.accentLight, color: KC.color.accent,
                    }}>Laufend</span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 16 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 11, color: dark ? KC.color.darkTextSec : KC.color.textTri, marginBottom: 2 }}>
                      Ausgaben
                    </div>
                    <div style={{ fontSize: 16, fontWeight: 600, fontVariantNumeric: 'tabular-nums', color: dark ? KC.color.darkText : KC.color.text }}>
                      €&thinsp;{y.paid.toLocaleString('de-AT', { minimumFractionDigits: 0 })}
                    </div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 11, color: dark ? KC.color.darkTextSec : KC.color.textTri, marginBottom: 2 }}>
                      Erstattet
                    </div>
                    <div style={{ fontSize: 16, fontWeight: 600, fontVariantNumeric: 'tabular-nums', color: '#16A34A' }}>
                      €&thinsp;{y.reimbursed.toLocaleString('de-AT', { minimumFractionDigits: 0 })}
                    </div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 11, color: dark ? KC.color.darkTextSec : KC.color.textTri, marginBottom: 2 }}>
                      Eigenanteil
                    </div>
                    <div style={{ fontSize: 16, fontWeight: 600, fontVariantNumeric: 'tabular-nums', color: '#EA580C' }}>
                      €&thinsp;{(y.paid - y.reimbursed).toLocaleString('de-AT', { minimumFractionDigits: 0 })}
                    </div>
                  </div>
                </div>
              </KCCard>
            ))}
          </div>
        )}

        {/* Members view */}
        {view === 'members' && (
          <div style={{ padding: '0 20px' }}>
            {memberTotals.map((m, i) => (
              <KCCard key={i} padding={16} style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
                  <KCAvatar initials={m.initials} color={m.color} size={40}/>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 15, fontWeight: 600, color: dark ? KC.color.darkText : KC.color.text }}>
                      {m.name} Kaiser
                    </div>
                    <div style={{ fontSize: 12, color: dark ? KC.color.darkTextSec : KC.color.textTri }}>
                      {m.count} Belege · 2026
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 12, marginBottom: 14 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 11, color: dark ? KC.color.darkTextSec : KC.color.textTri, marginBottom: 2 }}>
                      Ausgaben
                    </div>
                    <div style={{ fontSize: 18, fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: dark ? KC.color.darkText : KC.color.text }}>
                      €&thinsp;{m.paid.toLocaleString('de-AT', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    </div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 11, color: dark ? KC.color.darkTextSec : KC.color.textTri, marginBottom: 2 }}>
                      Erstattet
                    </div>
                    <div style={{ fontSize: 18, fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: '#16A34A' }}>
                      €&thinsp;{m.reimbursed.toLocaleString('de-AT', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    </div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 11, color: dark ? KC.color.darkTextSec : KC.color.textTri, marginBottom: 2 }}>
                      Eigenanteil
                    </div>
                    <div style={{ fontSize: 18, fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: '#EA580C' }}>
                      €&thinsp;{m.eigenanteil.toLocaleString('de-AT', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    </div>
                  </div>
                </div>

                {/* Mini bar showing member's share */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    flex: 1, height: 6, borderRadius: 3, overflow: 'hidden',
                    background: dark ? KC.color.darkSurfaceAlt : '#F0EFEC',
                  }}>
                    <div style={{
                      width: `${Math.min((m.paid / (memberTotals.reduce((s, mm) => s + mm.paid, 0) || 1)) * 100, 100)}%`,
                      height: '100%', borderRadius: 3, background: m.color, transition: 'width 0.5s',
                    }}/>
                  </div>
                  <span style={{ fontSize: 11, fontWeight: 600, color: m.color, minWidth: 32, textAlign: 'right' }}>
                    {Math.round((m.paid / (memberTotals.reduce((s, mm) => s + mm.paid, 0) || 1)) * 100)}%
                  </span>
                </div>
              </KCCard>
            ))}

            {/* Category breakdown */}
            <div style={{ marginTop: 12 }}>
              <div style={{
                fontSize: 14, fontWeight: 600, marginBottom: 10,
                color: dark ? KC.color.darkText : KC.color.text,
              }}>Nach Kategorie</div>
              <KCCard padding={0} style={{ overflow: 'hidden' }}>
                {categories.map((cat, i) => {
                  const pct = (cat.amount / totalPaid) * 100;
                  return (
                    <div key={i} style={{
                      padding: '12px 16px',
                      borderBottom: i < categories.length - 1 ? `1px solid ${dark ? KC.color.darkBorder : KC.color.borderLight}` : 'none',
                    }}>
                      <div style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6,
                      }}>
                        <span style={{ fontSize: 13, fontWeight: 500, color: dark ? KC.color.darkText : KC.color.text }}>
                          {cat.name}
                        </span>
                        <span style={{ fontSize: 13, fontWeight: 600, fontVariantNumeric: 'tabular-nums', color: dark ? KC.color.darkText : KC.color.text }}>
                          €&thinsp;{cat.amount.toLocaleString('de-AT', { minimumFractionDigits: 2 })}
                        </span>
                      </div>
                      <div style={{
                        height: 4, borderRadius: 2, overflow: 'hidden',
                        background: dark ? KC.color.darkSurfaceAlt : '#F0EFEC',
                      }}>
                        <div style={{
                          width: `${pct}%`, height: '100%', borderRadius: 2,
                          background: KC.color.accent, transition: 'width 0.5s',
                        }}/>
                      </div>
                    </div>
                  );
                })}
              </KCCard>
            </div>
          </div>
        )}
      </div>
    </KCPage>
  );
}

Object.assign(window, { StatsScreen });
