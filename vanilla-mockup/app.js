/* ==========================================================================
   SatyaPramaan AI — Client-Side Controller & Single Page Application Router
   ========================================================================== */

const app = {
    // Current application state
    state: {
        currentPath: '/',
        selectedDocIndex: 0,
        isScanning: false,
        activeApiLanguage: 'python',
        // Pre-loaded documents for the live demo panel
        preloadedDocs: [
            {
                id: 'DOC-9482',
                applicantName: 'Rajesh Kumar',
                docName: 'Sale Deed — Rajesh Kumar',
                uploadDate: '2026-06-05 14:20',
                riskScore: 92,
                riskLevel: 'HIGH',
                anomalies: [
                    { title: 'Arithmetic Area Conflict', desc: 'Declared property area (1,200 sq ft) in Sale Deed conflicts with municipal registry records which extract only 800 sq ft. (-33.3% area discrepancy)', severity: 'HIGH' },
                    { title: 'Signature Stamp Artifacts', desc: 'Signature block on Page 3 contains keypoint compression patterns indicating digital cut-and-paste stamp insertion.', severity: 'HIGH' },
                    { title: 'Font Style Outlier', desc: 'Typography engine detected Times-Roman character injections within a dominant Helvetica layout (indicating modification).', severity: 'HIGH' }
                ],
                llmSummary: 'Property area declared in the sale deed (1,200 sq ft) does not match the municipal record extract (800 sq ft). Signature on page 3 shows compression artifacts consistent with digital insertion. Overall Fraud Risk: HIGH. Recommended action: Request original physical documents and field verification.',
                docType: 'deed_forged' // mock view selector
            },
            {
                id: 'DOC-3829',
                applicantName: 'Priya Sharma',
                docName: 'ITR 2023-24 — Priya Sharma',
                uploadDate: '2026-06-03 10:15',
                riskScore: 55,
                riskLevel: 'MEDIUM',
                anomalies: [
                    { title: 'Software Editor Footprint', desc: 'PDF file metadata details reveal that the document was compiled and modified using "Nitro PDF Editor" instead of official IT Department compilers.', severity: 'MEDIUM' },
                    { title: 'Transaction Date Alert', desc: 'Modification timestamp is logged post tax submission window closing date.', severity: 'LOW' }
                ],
                llmSummary: 'Tax acknowledgement PDF files verify correct numerical totals, but structural headers detect editing software signatures. Recommended action: Perform cross-document audit against Form 26AS matching GST ledger records.',
                docType: 'itr_metadata'
            },
            {
                id: 'DOC-8210',
                applicantName: 'HDFC Banking Corp',
                docName: 'Bank Statement — HDFC',
                uploadDate: '2026-06-01 09:30',
                riskScore: 4,
                riskLevel: 'LOW',
                anomalies: [],
                llmSummary: 'Document integrity verified. Font hierarchy and metadata headers comply with HDFC bank statement native formatting models. Ledger transactions reconcile with employer salary payments.',
                docType: 'bank_genuine'
            }
        ],
        // Newly uploaded custom files
        uploadedDocs: []
    },

    // SEO Page Settings
    seoMetadata: {
        '/': {
            title: 'SatyaPramaan AI — Real-time Document Forgery Detection',
            desc: 'Detect document fraud before it becomes an NPA. Automate credit verification using CV-based pixel audits and LLM-powered risk insights.'
        },
        '/product': {
            title: 'Product & Technology Pipeline — SatyaPramaan AI',
            desc: 'Explore our 5-stage document verification pipeline featuring typography analysis, ELA forensics, cross-check matrix, and LLM evaluations.'
        },
        '/demo': {
            title: 'Interactive Underwriter Cockpit Demo — SatyaPramaan AI',
            desc: 'Simulate how bank credit underwriters detect document fraud using our interactive dashboard and AI risk summaries.'
        },
        '/use-cases': {
            title: 'Underwriting Use Cases — SatyaPramaan AI',
            desc: 'See how SatyaPramaan AI secures Home Loans, Business MSME Loans, and Agricultural/Land loans from fraud.'
        },
        '/integration': {
            title: 'Integration, REST APIs & SDKs — SatyaPramaan AI',
            desc: 'Plug SatyaPramaan AI directly into your core banking system in days using our simple REST APIs and Python SDK.'
        },
        '/pricing': {
            title: 'Flexible Plans for NBFCs & Banks — SatyaPramaan AI',
            desc: 'Browse starter, professional, and enterprise plans designed for modern banking networks and digital lenders.'
        },
        '/about': {
            title: 'About SatyaPramaan AI — Eliminating Loan Fraud',
            desc: 'Learn about our mission to secure India\'s credit systems and our expert team building specialized financial technology.'
        },
        '/contact': {
            title: 'Request a Live Demo — SatyaPramaan AI',
            desc: 'Schedule a tailored walkthrough with our banking solution architects and test SatyaPramaan AI on your own files.'
        }
    },

    // Initialization
    init: function() {
        this.initRouter();
        this.bindEvents();
        this.renderDemoDocs();
        this.loadDemoDoc(0);
        this.updateTimeBadge();
    },

    // 1. Client-Side Router
    initRouter: function() {
        const self = this;
        
        // Handle nav links clicking
        document.body.addEventListener('click', function(e) {
            const link = e.target.closest('[data-link]');
            if (link) {
                e.preventDefault();
                const path = link.getAttribute('href');
                self.navigate(path);
            }
        });

        // Handle browser Back/Forward buttons
        window.addEventListener('popstate', function() {
            self.resolveRoute(window.location.pathname);
        });

        // Resolve initial load route
        this.resolveRoute(window.location.pathname);
    },

    navigate: function(path) {
        window.history.pushState(null, '', path);
        this.resolveRoute(path);
    },

    resolveRoute: function(path) {
        // Normalize path
        let targetPath = path || '/';
        if (targetPath.length > 1 && targetPath.endsWith('/')) {
            targetPath = targetPath.slice(0, -1);
        }

        // Set default path if invalid
        if (!this.seoMetadata[targetPath]) {
            targetPath = '/';
        }

        this.state.currentPath = targetPath;
        
        // Update Title & Meta tags for SEO
        const metadata = this.seoMetadata[targetPath];
        if (metadata) {
            document.title = metadata.title;
            const metaDescription = document.querySelector('meta[name="description"]');
            if (metaDescription) {
                metaDescription.setAttribute('content', metadata.desc);
            }
        }

        // Switch visible viewports
        const marketingLayout = document.getElementById('marketing-layout');
        const demoLayout = document.getElementById('demo-layout');

        if (targetPath === '/demo') {
            // Fullscreen demo layout, hide marketing wrappers
            marketingLayout.classList.add('hidden');
            demoLayout.classList.remove('hidden');
            this.syncDemoLayout();
        } else {
            // Show marketing layout, hide demo wrapper
            demoLayout.classList.add('hidden');
            marketingLayout.classList.remove('hidden');

            // Toggle active page section
            const pageIdMap = {
                '/': 'page-home',
                '/product': 'page-product',
                '/use-cases': 'page-use-cases',
                '/integration': 'page-integration',
                '/pricing': 'page-pricing',
                '/about': 'page-about',
                '/contact': 'page-contact'
            };

            const targetSectionId = pageIdMap[targetPath] || 'page-home';
            const pageSections = document.querySelectorAll('.marketing-page');
            pageSections.forEach(section => {
                if (section.id === targetSectionId) {
                    section.classList.add('active');
                } else {
                    section.classList.remove('active');
                }
            });

            // Update nav links active classes
            const navLinks = document.querySelectorAll('.nav-link');
            navLinks.forEach(link => {
                if (link.getAttribute('href') === targetPath) {
                    link.classList.add('active');
                } else {
                    link.classList.remove('active');
                }
            });
        }

        // Scroll to top on navigation
        window.scrollTo(0, 0);
    },

    // 2. Event Binding
    bindEvents: function() {
        const self = this;

        // API Code snippet tabs switcher
        const apiTabBtns = document.querySelectorAll('.api-tab-btn');
        apiTabBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                apiTabBtns.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                const lang = this.getAttribute('data-lang');
                self.switchApiSnippetLanguage(lang);
            });
        });

        // FAQ accordion click toggling
        const faqItems = document.querySelectorAll('.faq-node-item');
        faqItems.forEach(item => {
            const trigger = item.querySelector('.faq-trigger-btn');
            const content = item.querySelector('.faq-panel-content');
            
            trigger.addEventListener('click', function() {
                const isActive = trigger.classList.contains('active');
                
                // Close all other accordions first
                faqItems.forEach(otherItem => {
                    otherItem.querySelector('.faq-trigger-btn').classList.remove('active');
                    otherItem.querySelector('.faq-panel-content').style.maxHeight = null;
                });

                if (!isActive) {
                    trigger.classList.add('active');
                    content.style.maxHeight = content.scrollHeight + "px";
                }
            });
        });

        // Demo Document Selection handler
        document.getElementById('demo-doc-list').addEventListener('click', function(e) {
            const docCard = e.target.closest('.demo-doc-card');
            if (docCard) {
                const index = parseInt(docCard.getAttribute('data-index'));
                self.loadDemoDoc(index);
            }
        });

        // Demo filter selector handler
        const filterSelect = document.getElementById('demo-filter-risk');
        if (filterSelect) {
            filterSelect.addEventListener('change', function() {
                self.renderDemoDocs();
            });
        }

        // Demo search field handler
        const searchInput = document.getElementById('demo-search');
        if (searchInput) {
            searchInput.addEventListener('input', function() {
                self.renderDemoDocs();
            });
        }

        // File upload click trigger for demo
        const uploadZone = document.getElementById('demo-upload-zone');
        const fileInput = document.getElementById('demo-file-input');
        if (uploadZone && fileInput) {
            uploadZone.addEventListener('click', () => fileInput.click());
            
            uploadZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadZone.style.borderColor = '#8b5cf6';
                uploadZone.style.backgroundColor = 'rgba(99, 102, 241, 0.05)';
            });

            uploadZone.addEventListener('dragleave', () => {
                uploadZone.style.borderColor = 'var(--border-color)';
                uploadZone.style.backgroundColor = 'transparent';
            });

            uploadZone.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadZone.style.borderColor = 'var(--border-color)';
                uploadZone.style.backgroundColor = 'transparent';
                if (e.dataTransfer.files.length > 0) {
                    self.handleDemoUploadedFile(e.dataTransfer.files[0]);
                }
            });

            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    self.handleDemoUploadedFile(e.target.files[0]);
                }
            });
        }

        // Contact demo request form validation & submission
        const contactForm = document.getElementById('demo-request-form');
        if (contactForm) {
            contactForm.addEventListener('submit', function(e) {
                e.preventDefault();
                self.handleFormSubmit(this);
            });
        }

        // Close Success modal popup button
        const closeModalBtn = document.getElementById('close-success-modal');
        if (closeModalBtn) {
            closeModalBtn.addEventListener('click', function() {
                document.getElementById('success-modal').classList.remove('active');
            });
        }

        // Export Audit Trail print event
        const exportBtn = document.getElementById('demo-export-btn');
        if (exportBtn) {
            exportBtn.addEventListener('click', function() {
                self.triggerAuditExport();
            });
        }
    },

    // 3. Marketing Interactive Handlers
    switchApiSnippetLanguage: function(lang) {
        this.state.activeApiLanguage = lang;
        const codeBlocks = document.querySelectorAll('.api-code-block');
        codeBlocks.forEach(block => {
            if (block.id === `code-${lang}`) {
                block.classList.remove('hidden');
            } else {
                block.classList.add('hidden');
            }
        });
    },

    handleFormSubmit: function(form) {
        // Simple client validations
        const email = form.querySelector('[type="email"]').value;
        const phone = form.querySelector('[type="tel"]').value;
        
        if (!email || !email.includes('@')) {
            alert('Please enter a valid work email.');
            return;
        }

        if (phone.length < 10) {
            alert('Please enter a valid phone number.');
            return;
        }

        // Success state modal popup trigger
        const modal = document.getElementById('success-modal');
        modal.classList.add('active');
        form.reset();
    },

    // 4. Interactive Live Demo Controls
    syncDemoLayout: function() {
        this.renderDemoDocs();
        this.loadDemoDoc(this.state.selectedDocIndex);
    },

    getAllDocs: function() {
        return [...this.state.uploadedDocs, ...this.state.preloadedDocs];
    },

    renderDemoDocs: function() {
        const container = document.getElementById('demo-doc-list');
        if (!container) return;

        const filter = document.getElementById('demo-filter-risk')?.value || 'ALL';
        const search = document.getElementById('demo-search')?.value.toLowerCase() || '';

        container.innerHTML = '';
        const allDocs = this.getAllDocs();

        allDocs.forEach((doc, idx) => {
            // Apply filtering rules
            const textMatch = doc.docName.toLowerCase().includes(search) || 
                              doc.applicantName.toLowerCase().includes(search) ||
                              doc.id.toLowerCase().includes(search);

            let riskMatch = true;
            if (filter !== 'ALL') {
                riskMatch = doc.riskLevel === filter;
            }

            if (!textMatch || !riskMatch) return;

            const card = document.createElement('div');
            const isActive = idx === this.state.selectedDocIndex;
            card.className = `demo-doc-card ${isActive ? 'active' : ''}`;
            card.setAttribute('data-index', idx);

            card.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom: 6px;">
                    <span style="font-size:12.5px; font-weight:700; color:var(--text-primary);">${doc.applicantName}</span>
                    <span class="demo-doc-risk-label ${doc.riskLevel.toLowerCase()}">${doc.riskLevel}</span>
                </div>
                <div class="demo-doc-name-row" style="margin-bottom:6px;">
                    <div class="demo-doc-icon-wrapper" style="margin-top:2px;">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                        </svg>
                    </div>
                    <span class="demo-doc-title" style="font-size:11px; color:var(--text-secondary);">${doc.docName}</span>
                </div>
                <div class="demo-doc-meta-row">
                    <span>${doc.id} • ${doc.uploadDate.split(' ')[0]}</span>
                    <span>Score: <strong>${doc.riskScore}%</strong></span>
                </div>
            `;
            container.appendChild(card);
        });
    },

    loadDemoDoc: function(index) {
        const allDocs = this.getAllDocs();
        if (index >= allDocs.length || index < 0) return;

        this.state.selectedDocIndex = index;
        const doc = allDocs[index];

        // Highlight active sidebar item
        const cards = document.querySelectorAll('.demo-doc-card');
        cards.forEach(card => {
            if (parseInt(card.getAttribute('data-index')) === index) {
                card.classList.add('active');
            } else {
                card.classList.remove('active');
            }
        });

        // Set core layout details
        document.getElementById('demo-viewer-filename').textContent = doc.docName;
        document.getElementById('demo-viewer-id').innerHTML = `Applicant: <strong>${doc.applicantName}</strong> &nbsp;|&nbsp; Ref: <strong>${doc.id}</strong> &nbsp;|&nbsp; Date: <strong>${doc.uploadDate}</strong>`;

        // Set Risk badge
        const riskBadge = document.getElementById('demo-risk-badge');
        riskBadge.textContent = `${doc.riskLevel} RISK (${doc.riskScore}%)`;
        riskBadge.className = `demo-doc-risk-label ${doc.riskLevel.toLowerCase()}`;

        // Set LLM insights summary
        document.getElementById('demo-llm-summary-text').textContent = doc.llmSummary;

        // Render Anomalies list
        const anomaliesContainer = document.getElementById('demo-anomalies-list');
        anomaliesContainer.innerHTML = '';

        if (doc.anomalies.length === 0) {
            anomaliesContainer.innerHTML = `
                <li style="font-size: 12px; color: var(--text-muted); list-style: none;">
                    ✓ No anomalies or typography mismatches detected by the scanner.
                </li>
            `;
        } else {
            doc.anomalies.forEach(an => {
                const li = document.createElement('li');
                li.className = 'demo-anomaly-bullet-item';
                li.innerHTML = `
                    <span class="demo-anomaly-bullet-dot ${an.severity.toLowerCase()}"></span>
                    <div>
                        <strong>${an.title}</strong>
                        <p style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">${an.desc}</p>
                    </div>
                `;
                anomaliesContainer.appendChild(li);
            });
        }

        // Render Visual Document Preview Mockup
        this.renderDocumentPreview(doc);
    },

    renderDocumentPreview: function(doc) {
        const canvas = document.getElementById('demo-viewer-canvas');
        canvas.innerHTML = '';

        // If it\'s a custom upload with raw HTML output (such as font analysis lines list)
        if (doc.customHTML) {
            canvas.innerHTML = doc.customHTML;
            return;
        }

        // For preloaded docs, we render pixel-perfect CSS-designed sheets
        if (doc.docType === 'deed_forged') {
            canvas.innerHTML = `
                <div class="mock-deed-document">
                    <div class="mock-deed-header">SALE DEED / CONVEYANCE DEED</div>
                    <div class="mock-deed-stamp">SUSPICIOUS<br>STAMP</div>
                    <div class="mock-deed-row">
                        THIS INDENTURE is made at Electronic City, Bangalore between <strong>Karan Singh</strong> 
                        (Vendor) and <strong>Rajesh Kumar</strong> (Purchaser).
                    </div>
                    <div class="mock-deed-row">
                        <strong>SUBJECT PROPERTY:</strong> Residential plot located at survey number 404, measuring 
                        <span class="mock-deed-highlight-box" data-tooltip="CONFLICT: Municipal survey database declares only 800 sq ft.">1,200 sq ft</span>.
                    </div>
                    <div class="mock-deed-row">
                        <strong>CONSIDERATION:</strong> Sum of Rs. 45,00,000.00 (Forty-Five Lakhs Rupees) transferred via ACH bank credits.
                    </div>
                    <div class="mock-deed-row" style="margin-top: 40px;">
                        IN WITNESS WHEREOF the parties hereto have signed this deed on 25th November 2025.
                    </div>
                    <div class="mock-deed-footer">
                        <div>
                            Witness 1: Amit Verma<br>
                            Witness 2: Priya Sharma
                        </div>
                        <div class="mock-deed-signature-box" data-tooltip="ELA FORENSICS: Sig block compression values outlier (+14.2% residual variance)">
                            Vendor Signature
                            <div class="mock-deed-signature">Karan Singh</div>
                        </div>
                    </div>
                </div>
            `;
        } else if (doc.docType === 'itr_metadata') {
            canvas.innerHTML = `
                <div class="mock-deed-document" style="font-family: sans-serif; font-size: 10px;">
                    <div class="mock-deed-header" style="font-size:11px;">INCOME TAX RETURN ACKNOWLEDGEMENT (ITR-V)</div>
                    <div class="mock-deed-stamp verified" style="font-size:7px; top:30px;">METADATA<br>WARNING</div>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px;">
                        <div>
                            <strong>PAN:</strong> BPHPS2930K<br>
                            <strong>Assessment Year:</strong> 2023-24<br>
                            <strong>Status:</strong> INDIVIDUAL
                        </div>
                        <div style="text-align:right;">
                            <strong>Name:</strong> Priya Sharma<br>
                            <strong>Filing Date:</strong> 31-Jul-2023<br>
                            <strong>Receipt No:</strong> 2940294829
                        </div>
                    </div>
                    <div style="border: 1px solid #000; padding:10px; margin-bottom:12px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                            <span>1. Gross Total Income</span>
                            <span><strong>Rs. 15,45,000.00</strong></span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                            <span>2. Total Deductions (Chapter VI-A)</span>
                            <span>Rs. 1,50,000.00</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; border-top:1px solid #000; padding-top:6px;">
                            <span>3. Net Taxable Income</span>
                            <span><strong>Rs. 13,95,000.00</strong></span>
                        </div>
                    </div>
                    <div style="font-size:8px; color:#475569; margin-top:30px; border-top:1px dashed #cbd5e1; padding-top:10px;">
                        * This acknowledgement is automatically compiled. <span class="mock-deed-highlight-box" style="font-size:8px;" data-tooltip="METADATA ALERT: Document headers trace edit software footprint 'Nitro PDF Editor'.">File modified signature detected.</span>
                    </div>
                </div>
            `;
        } else if (doc.docType === 'bank_genuine') {
            canvas.innerHTML = `
                <div class="mock-deed-document" style="font-family: sans-serif; font-size: 9.5px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom: 2px solid #1e3a8a; padding-bottom:10px; margin-bottom:20px;">
                        <strong style="color:#1e3a8a; font-size:14px;">HDFC BANK</strong>
                        <span>Statement of Account (Nov 2025)</span>
                    </div>
                    <div style="margin-bottom:16px;">
                        <strong>Name:</strong> Karan Singh<br>
                        <strong>Account No:</strong> 50100482948201<br>
                        <strong>Branch:</strong> Electronic City Bangalore
                    </div>
                    <table style="width:100%; font-size:9px; border-collapse:collapse; margin-top:12px;">
                        <thead>
                            <tr style="background-color:#f8fafc; border-bottom: 1px solid #cbd5e1;">
                                <th style="text-align:left; padding:6px;">Date</th>
                                <th style="text-align:left; padding:6px;">Description</th>
                                <th style="text-align:right; padding:6px;">Chq/Ref</th>
                                <th style="text-align:right; padding:6px;">Credit</th>
                                <th style="text-align:right; padding:6px;">Balance</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr style="border-bottom: 1px solid #e2e8f0;">
                                <td style="padding:6px;">01-Nov-2025</td>
                                <td style="padding:6px;">B/F Balance</td>
                                <td style="padding:6px; text-align:right;">-</td>
                                <td style="padding:6px; text-align:right;">-</td>
                                <td style="padding:6px; text-align:right;">Rs. 42,940.50</td>
                            </tr>
                            <tr style="border-bottom: 1px solid #e2e8f0;">
                                <td style="padding:6px;">25-Nov-2025</td>
                                <td style="padding:6px;">APEX TECH SOLUTIONS SALARY</td>
                                <td style="padding:6px; text-align:right;">ACH94829</td>
                                <td style="padding:6px; text-align:right; color:#10b981; font-weight:700;">Rs. 1,33,000.00</td>
                                <td style="padding:6px; text-align:right;">Rs. 1,75,940.50</td>
                            </tr>
                            <tr style="border-bottom: 1px solid #e2e8f0;">
                                <td style="padding:6px;">28-Nov-2025</td>
                                <td style="padding:6px;">ATM WDL - HDFC BOMBAY</td>
                                <td style="padding:6px; text-align:right;">ATM4019</td>
                                <td style="padding:6px; text-align:right; color:#ef4444;">-10,000.00</td>
                                <td style="padding:6px; text-align:right;">Rs. 1,65,940.50</td>
                            </tr>
                        </tbody>
                    </table>
                    <div style="margin-top:30px; text-align:center; font-size:8px; color:#10b981;">
                        ✓ HDFC Bank Statement Structure and font verification: 100% genuine structure match.
                    </div>
                </div>
            `;
        }
    },

    // 5. FastAPI Live Upload Audit Integrations
    handleDemoUploadedFile: function(file) {
        if (this.state.isScanning) return;
        this.state.isScanning = true;

        const laser = document.getElementById('demo-laser-overlay');
        const statusCard = document.getElementById('demo-laser-status');
        
        laser.classList.add('active');
        statusCard.textContent = "Scanning document vectors...";

        // Set scanning timers to simulate pipeline stages
        setTimeout(() => { statusCard.textContent = "Matching font structures..."; }, 600);
        setTimeout(() => { statusCard.textContent = "Checking pixel discrepancies..."; }, 1200);
        setTimeout(() => { statusCard.textContent = "Generating plain-English risk audit..."; }, 1800);

        const formData = new FormData();
        formData.append("file", file);

        fetch("/api/scan", {
            method: "POST",
            body: formData
        })
        .then(res => {
            if (!res.ok) return res.json().then(e => { throw new Error(e.detail || "Server verification error") });
            return res.json();
        })
        .then(data => {
            setTimeout(() => {
                laser.classList.remove('active');
                this.state.isScanning = false;

                // Create a new uploaded document layout structure
                let customHTML = '';
                const isPdf = data.file_type === 'pdf';

                if (isPdf) {
                    // Reconstruct text lines
                    let lines = '';
                    if (data.extracted_data && data.extracted_data.name) {
                        lines += `<div class="pdf-line"><strong>Verification Report: ${data.filename}</strong></div>`;
                        lines += `<div class="pdf-line">------------------------------------</div>`;
                        lines += `<div class="pdf-line">Applicant Name:   ${data.extracted_data.name}</div>`;
                        lines += `<div class="pdf-line">PAN Card linked:  ${data.extracted_data.pan}</div>`;
                        lines += `<div class="pdf-line">Net salary value: ${data.extracted_data.net_pay}</div>`;
                        lines += `<div class="pdf-line">------------------------------------</div>`;
                    } else {
                        lines += `<div class="pdf-line"><strong>Verification Report: ${data.filename}</strong></div>`;
                        lines += `<div class="pdf-line">Structure verified. Character length: ${data.anomalies.length} entries.</div>`;
                    }

                    // Append alerts if present
                    if (data.anomalies.length > 0) {
                        lines += `<div class="pdf-line" style="color:red; margin-top:20px;"><strong>CRITICAL ANOMALIES HIGHLIGHTED:</strong></div>`;
                        data.anomalies.forEach(a => {
                            lines += `<div class="pdf-line" style="color:red;">• ${a.title}: ${a.desc}</div>`;
                        });
                    } else {
                        lines += `<div class="pdf-line" style="color:green; margin-top:20px;">✓ Passed typography audits with zero inconsistencies.</div>`;
                    }

                    customHTML = `
                        <div class="pdf-text-viewer" style="width:100%; max-width:440px; height:auto; box-shadow:none;">
                            ${lines}
                        </div>
                    `;
                } else {
                    // Render image ELA heatmap preview side by side
                    customHTML = `
                        <div class="image-ela-viewer" style="width:100%; height:auto;">
                            <div class="ela-pane" style="background:#0b0f19;">
                                <span class="ela-label">ORIGINAL</span>
                                <img src="/uploads/${data.filename}" style="max-height:240px; object-fit:contain;">
                            </div>
                            <div class="ela-pane" style="background:#0b0f19;">
                                <span class="ela-label red">ELA HEATMAP</span>
                                <img src="${data.ela_image_url}" style="max-height:240px; object-fit:contain;">
                            </div>
                        </div>
                    `;
                }

                // Add to uploaded array state
                const newDoc = {
                    id: `UPLOAD-${Math.floor(1000 + Math.random()*9000)}`,
                    applicantName: data.extracted_data.name || 'External Upload',
                    docName: data.filename,
                    uploadDate: new Date().toISOString().slice(0, 16).replace('T', ' '),
                    riskScore: data.risk_score,
                    riskLevel: data.risk_level,
                    anomalies: data.anomalies.map(a => ({ title: a.title, desc: a.desc, severity: a.severity })),
                    llmSummary: data.llm_insight.replace(/<[^>]*>/g, ''), // strip html tags for demo box
                    customHTML: customHTML
                };

                this.state.uploadedDocs.unshift(newDoc);
                
                // Select the uploaded item (since it goes to front of array, it is index 0)
                this.renderDemoDocs();
                this.loadDemoDoc(0);
            }, 2400);
        })
        .catch(err => {
            console.error("Scanning failed:", err);
            laser.classList.remove('active');
            this.state.isScanning = false;
            alert("FastAPI backend error: " + err.message);
        });
    },

    // 6. Print Audit Trail report dialog triggering
    triggerAuditExport: function() {
        const doc = this.getAllDocs()[this.state.selectedDocIndex];
        const printWindow = window.open('', '_blank');
        
        let anomaliesList = '';
        if (doc.anomalies.length === 0) {
            anomaliesList = '<p>No anomalies detected. File integrity verified.</p>';
        } else {
            anomaliesList = '<ul>';
            doc.anomalies.forEach(a => {
                anomaliesList += `
                    <li style="margin-bottom:12px;">
                        <strong>[${a.severity} SEVERITY] ${a.title}</strong><br>
                        ${a.desc}
                    </li>
                `;
            });
            anomaliesList += '</ul>';
        }

        printWindow.document.write(`
            <html>
            <head>
                <title>SatyaPramaan Audit Report — ${doc.id}</title>
                <style>
                    body { font-family: -apple-system, sans-serif; color: #1e293b; padding: 40px; line-height: 1.6; }
                    .header { border-bottom: 3px double #000; padding-bottom: 15px; margin-bottom: 30px; }
                    .header h1 { font-size: 24px; margin: 0; text-transform: uppercase; }
                    .header p { color: #64748b; margin: 4px 0 0; font-size: 13px; }
                    .meta-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; background: #f8fafc; padding: 15px; border-radius: 6px; }
                    .meta-item { font-size: 13px; }
                    .section { margin-bottom: 30px; }
                    .section h3 { border-bottom: 1px solid #cbd5e1; padding-bottom: 6px; font-size: 16px; text-transform: uppercase; }
                    .risk-box { background: #fee2e2; border: 1px solid #fca5a5; color: #991b1b; padding: 15px; border-radius: 6px; margin-bottom: 30px; font-weight: bold; }
                    .risk-box.low { background: #d1fae5; border-color: #6ee7b7; color: #065f46; }
                    .risk-box.medium { background: #ffedd5; border-color: #fdba74; color: #9a3412; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>SatyaPramaan AI — Underwriter Verification Trail</h1>
                    <p>Compliance Audit Record ID: SP-${doc.id}</p>
                </div>
                
                <div class="risk-box ${doc.riskLevel.toLowerCase()}">
                    OVERALL FRAUD RISK: ${doc.riskLevel} (${doc.riskScore}% Probability)
                </div>

                <div class="meta-grid">
                    <div class="meta-item">
                        <strong>Applicant Profile:</strong> ${doc.applicantName}<br>
                        <strong>Document Name:</strong> ${doc.docName}
                    </div>
                    <div class="meta-item">
                        <strong>Generated On:</strong> ${new Date().toLocaleString()}<br>
                        <strong>Upload Date:</strong> ${doc.uploadDate}
                    </div>
                </div>

                <div class="section">
                    <h3>AI Risk Evaluator Summary</h3>
                    <p>${doc.llmSummary}</p>
                </div>

                <div class="section">
                    <h3>Flagged Structural Anomalies</h3>
                    ${anomaliesList}
                </div>

                <div style="margin-top: 50px; font-size: 11px; color: #94a3b8; border-top: 1px solid #cbd5e1; padding-top: 20px;">
                    This document is cryptographically logged under secure blockchain/database registers. SatyaPramaan verification processes do not compromise user data safety limits conforming strictly to RBI directives.
                </div>
                <script>
                    window.onload = function() { window.print(); }
                </script>
            </body>
            </html>
        `);
        printWindow.document.close();
    },

    // 7. Dynamic UI current date badge
    updateTimeBadge: function() {
        const timeEl = document.getElementById('current-time');
        const demoTimeEl = document.getElementById('demo-current-time');
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const d = new Date();
        const dateString = `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
        
        if (timeEl) timeEl.textContent = dateString;
        if (demoTimeEl) demoTimeEl.textContent = dateString;
    }
};

// Initialize Application once DOM compiles
document.addEventListener('DOMContentLoaded', () => {
    app.init();
});
