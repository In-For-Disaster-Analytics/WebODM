import React from 'react';
import ReactDOM from 'ReactDOM';
import PropTypes from 'prop-types';
import $ from 'jquery';

// ── Minimal markdown renderer ─────────────────────────────────────────────────

function inlineMarkdown(text) {
    // **bold** and `code`
    const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/);
    return parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**'))
            return <strong key={i}>{part.slice(2, -2)}</strong>;
        if (part.startsWith('`') && part.endsWith('`'))
            return <code key={i} style={{ background: '#eee', borderRadius: 2, padding: '0 3px', fontSize: 11 }}>{part.slice(1, -1)}</code>;
        return part;
    });
}

function renderMarkdown(text) {
    const lines = (text || '').split('\n');
    const out = [];
    let listItems = [];
    let key = 0;

    const flushList = () => {
        if (!listItems.length) return;
        out.push(
            <ul key={key++} style={{ margin: '2px 0 4px 14px', padding: 0 }}>
                {listItems}
            </ul>
        );
        listItems = [];
    };

    lines.forEach(line => {
        if (/^###?\s/.test(line)) {
            flushList();
            const text = line.replace(/^###?\s/, '');
            out.push(
                <div key={key++} style={{ fontWeight: 700, fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 10, marginBottom: 2 }}>
                    {text}
                </div>
            );
        } else if (line.startsWith('- ')) {
            listItems.push(
                <li key={key++} style={{ fontSize: 12, lineHeight: 1.5 }}>{inlineMarkdown(line.slice(2))}</li>
            );
        } else if (line.trim() === '') {
            flushList();
            out.push(<div key={key++} style={{ height: 5 }} />);
        } else {
            flushList();
            out.push(
                <div key={key++} style={{ fontSize: 12, lineHeight: 1.5 }}>{inlineMarkdown(line)}</div>
            );
        }
    });
    flushList();
    return out;
}

const POLL_INTERVAL = 3000;

export default class CKANPublishPanel extends React.Component {
    static defaultProps = {
        task: null,
    };

    static propTypes = {
        task: PropTypes.object.isRequired,
    };

    constructor(props) {
        super(props);
        this.state = {
            panelOpen: false,
            messages: [],
            inputText: '',
            threadId: null,
            agentStatus: null,
            publishStatus: 'idle',   // idle | publishing | success | error
            publishMessage: '',      // phase message from the Celery task (polled)
            ckanUrl: props.task.ckan_url || '',
            error: '',
            loading: false,
            inputLocked: false,
        };
        this._pollTimer = null;
    }

    componentWillUnmount() {
        this._stopPolling();
    }

    _stopPolling() {
        if (this._pollTimer) {
            clearInterval(this._pollTimer);
            this._pollTimer = null;
        }
    }

    _startPolling() {
        this._stopPolling();
        this._pollTimer = setInterval(this._pollStatus, POLL_INTERVAL);
    }

    _pollStatus = () => {
        const { task } = this.props;
        $.ajax({
            type: 'GET',
            url: `/api/plugins/ckan/task/${task.id}/publish-status`,
        }).done(data => {
            const prevStatus = this.state.publishStatus;
            this.setState({
                publishStatus: data.status,
                publishMessage: data.message || '',
                ckanUrl: data.ckan_url || this.state.ckanUrl,
                error: data.error || '',
            });
            if (data.status === 'success') {
                this._stopPolling();
                if (prevStatus !== 'success') {
                    const text = data.message
                        ? `Published successfully. ${data.message}`
                        : 'Published successfully.';
                    this._appendMessage('agent', text);
                }
            } else if (data.status === 'error') {
                this._stopPolling();
            }
        }).fail(() => {
            // silent — keep polling
        });
    }

    _appendMessage(role, text) {
        this.setState(prev => ({
            messages: [...prev.messages, { role, text }],
        }));
    }

    handleOpenPanel = () => {
        const { task } = this.props;
        this.setState({ panelOpen: true, loading: true, error: '', messages: [] });

        $.ajax({
            type: 'POST',
            url: `/api/plugins/ckan/task/${task.id}/chat/start`,
            contentType: 'application/json',
            data: JSON.stringify({}),
        }).done(data => {
            this.setState({
                threadId: data.thread_id,
                agentStatus: data.status,
                loading: false,
            });
            this._appendMessage('agent', data.message || '(no response)');
        }).fail(xhr => {
            const msg = (xhr.responseJSON && xhr.responseJSON.error) || xhr.statusText;
            this.setState({ error: msg, loading: false });
        });
    }

    handleSend = () => {
        const { task } = this.props;
        const { threadId, inputText } = this.state;
        if (!inputText.trim() || !threadId) return;

        const userMsg = inputText.trim();
        this._appendMessage('user', userMsg);
        this.setState({ inputText: '', loading: true });

        $.ajax({
            type: 'POST',
            url: `/api/plugins/ckan/task/${task.id}/chat/message`,
            contentType: 'application/json',
            data: JSON.stringify({ thread_id: threadId, message: userMsg }),
        }).done(data => {
            this.setState({ agentStatus: data.status, loading: false });
            this._appendMessage('agent', data.message || '(no response)');
        }).fail(xhr => {
            const msg = (xhr.responseJSON && xhr.responseJSON.error) || xhr.statusText;
            this.setState({ error: msg, loading: false });
        });
    }

    handleConfirm = () => {
        const { task } = this.props;
        const { threadId } = this.state;
        if (!threadId) return;

        this.setState({ inputLocked: true, publishStatus: 'publishing', error: '' });

        $.ajax({
            type: 'POST',
            url: `/api/plugins/ckan/task/${task.id}/chat/confirm`,
            contentType: 'application/json',
            data: JSON.stringify({ thread_id: threadId }),
        }).done(() => {
            this._appendMessage('agent', 'Publishing to CKAN… this may take a minute.');
            this._startPolling();
        }).fail(xhr => {
            const msg = (xhr.responseJSON && xhr.responseJSON.error) || xhr.statusText;
            this.setState({ error: msg, publishStatus: 'error', inputLocked: false });
        });
    }

    handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.handleSend();
        }
    }

    renderButton() {
        const { ckanUrl } = this.state;

        if (ckanUrl) {
            return (
                <span>
                    <a
                        href={ckanUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-sm btn-success"
                    >
                        <i className="fa fa-check" /> Published to CKAN ↗
                    </a>
                    {' '}
                    <button
                        className="btn btn-sm btn-default"
                        onClick={this.handleOpenPanel}
                    >
                        Re-publish
                    </button>
                </span>
            );
        }

        return (
            <button className="btn btn-sm btn-primary" onClick={this.handleOpenPanel}>
                <i className="fa fa-upload" /> Publish to CKAN
            </button>
        );
    }

    renderPanel() {
        const { messages, inputText, publishStatus, publishMessage, ckanUrl, error, loading, inputLocked } = this.state;

        const modal = (
            <div style={styles.backdrop} onClick={() => this.setState({ panelOpen: false })}>
            <div style={styles.panel} onClick={e => e.stopPropagation()}>
                <div style={styles.header}>
                    <strong>Publish to CKAN</strong>
                    <button
                        style={styles.closeBtn}
                        onClick={() => this.setState({ panelOpen: false })}
                    >
                        ✕
                    </button>
                </div>

                <div style={styles.chatArea} ref={el => { this._chatArea = el; }}>
                    {messages.map((m, i) => (
                        <div
                            key={i}
                            style={m.role === 'user' ? styles.userMsg : styles.agentMsg}
                        >
                            {m.role === 'user'
                                ? <div style={styles.msgText}>{m.text}</div>
                                : renderMarkdown(m.text)
                            }
                        </div>
                    ))}
                    {loading && (
                        <div style={styles.agentMsg}>
                            <i className="fa fa-circle-notch fa-spin" /> Thinking…
                        </div>
                    )}
                    {publishStatus === 'publishing' && publishMessage && (
                        <div style={styles.phaseMsg}>
                            <i className="fa fa-circle-notch fa-spin" /> {publishMessage}
                        </div>
                    )}
                    {publishStatus === 'success' && ckanUrl && (
                        <div style={styles.successMsg}>
                            Published ✓ —{' '}
                            <a href={ckanUrl} target="_blank" rel="noopener noreferrer">
                                View on CKAN →
                            </a>
                        </div>
                    )}
                    {error && (
                        <div style={styles.errorMsg}>Error: {error}</div>
                    )}
                </div>

                <div style={styles.inputRow}>
                    <textarea
                        style={styles.textarea}
                        value={inputText}
                        onChange={e => this.setState({ inputText: e.target.value })}
                        onKeyDown={this.handleKeyDown}
                        placeholder="Type a correction or press Enter to send…"
                        disabled={inputLocked || loading}
                        rows={2}
                    />
                    <button
                        className="btn btn-sm btn-default"
                        onClick={this.handleSend}
                        disabled={inputLocked || loading || !inputText.trim()}
                        style={styles.sendBtn}
                    >
                        Send
                    </button>
                </div>

                <div style={styles.confirmRow}>
                    <button
                        className="btn btn-sm btn-success"
                        onClick={this.handleConfirm}
                        disabled={inputLocked || loading || publishStatus === 'publishing'}
                    >
                        {publishStatus === 'publishing'
                            ? <span><i className="fa fa-circle-notch fa-spin" /> Publishing…</span>
                            : 'Confirm & Publish'}
                    </button>
                    {publishStatus === 'error' && (
                        <button
                            className="btn btn-sm btn-warning"
                            onClick={() => this.setState({ publishStatus: 'idle', inputLocked: false, error: '' })}
                            style={{ marginLeft: 8 }}
                        >
                            Retry
                        </button>
                    )}
                </div>
            </div>
            </div>
        );
        return ReactDOM.createPortal(modal, document.body);
    }

    componentDidUpdate(_, prevState) {
        if (prevState.messages.length !== this.state.messages.length && this._chatArea) {
            this._chatArea.scrollTop = this._chatArea.scrollHeight;
        }
    }

    render() {
        const { panelOpen } = this.state;

        return (
            <span style={styles.wrapper}>
                {this.renderButton()}
                {panelOpen && this.renderPanel()}
            </span>
        );
    }
}

const styles = {
    wrapper: {
        display: 'inline-block',
    },
    backdrop: {
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        background: 'rgba(0,0,0,0.35)',
        zIndex: 1000000,   // above WebODM navbar (99999) and modal (999999)
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
    },
    panel: {
        position: 'relative',
        width: 520,
        maxWidth: '92vw',
        maxHeight: '85vh',
        background: '#fff',
        border: '1px solid #ccc',
        borderRadius: 6,
        boxShadow: '0 8px 32px rgba(0,0,0,0.22)',
        zIndex: 1000001,
        display: 'flex',
        flexDirection: 'column',
    },
    header: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '8px 12px',
        borderBottom: '1px solid #eee',
        background: '#f8f8f8',
        borderRadius: '4px 4px 0 0',
    },
    closeBtn: {
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        fontSize: 16,
    },
    chatArea: {
        flex: 1,
        overflowY: 'auto',
        maxHeight: 340,
        padding: 12,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
    },
    agentMsg: {
        alignSelf: 'flex-start',
        background: '#f0f4ff',
        borderRadius: 6,
        padding: '6px 10px',
        maxWidth: '90%',
    },
    userMsg: {
        alignSelf: 'flex-end',
        background: '#e6f4ea',
        borderRadius: 6,
        padding: '6px 10px',
        maxWidth: '90%',
        textAlign: 'right',
    },
    msgText: {
        fontSize: 13,
    },
    phaseMsg: {
        alignSelf: 'flex-start',
        color: '#666',
        fontStyle: 'italic',
        fontSize: 12,
        padding: '2px 0',
    },
    successMsg: {
        color: '#2d7a2d',
        fontWeight: 'bold',
        padding: '4px 0',
    },
    errorMsg: {
        color: '#c0392b',
        padding: '4px 0',
        fontSize: 13,
    },
    inputRow: {
        display: 'flex',
        borderTop: '1px solid #eee',
        padding: 8,
        gap: 6,
    },
    textarea: {
        flex: 1,
        resize: 'none',
        border: '1px solid #ccc',
        borderRadius: 3,
        padding: '4px 8px',
        fontSize: 13,
    },
    sendBtn: {
        alignSelf: 'flex-end',
    },
    confirmRow: {
        padding: '6px 12px 10px',
        borderTop: '1px solid #eee',
    },
};
