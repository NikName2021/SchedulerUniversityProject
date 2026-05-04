import React, { useState, useEffect, useRef } from 'react';
import { 
  Folder,
  FileUp, 
  FileText, 
  CheckCircle2, 
  Trash2,
  ArrowLeft
} from 'lucide-react';

const DragDropZone = ({ onDrop, isDragging, setIsDragging }: { 
  onDrop: (files: FileList) => void, 
  isDragging: boolean, 
  setIsDragging: (val: boolean) => void 
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onDrop(e.target.files);
    }
  };

  return (
  <div 
    onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
    onDragLeave={() => setIsDragging(false)}
    onDrop={(e) => {
      e.preventDefault();
      setIsDragging(false);
      if (e.dataTransfer.files) onDrop(e.dataTransfer.files);
    }}
    style={{
      border: `2px dashed ${isDragging ? 'var(--brand)' : 'var(--border-light)'}`,
      borderRadius: '32px',
      padding: '4rem 2rem',
      textAlign: 'center',
      backgroundColor: isDragging ? 'var(--bg-base)' : 'white',
      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      cursor: 'pointer',
      transform: isDragging ? 'scale(1.02)' : 'scale(1)'
    }}
    className="group"
  >
    <div style={{
      width: '64px',
      height: '64px',
      backgroundColor: isDragging ? 'var(--brand)' : 'var(--bg-base)',
      color: isDragging ? 'white' : 'var(--brand)',
      borderRadius: '20px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      margin: '0 auto 1.5rem',
      transition: 'all 0.3s'
    }}>
      <FileUp size={32} />
    </div>
    <h3 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: '0.5rem' }}>
      Перетащите Excel-файлы сюда
    </h3>
    <p className="text-text-secondary" style={{ maxWidth: '400px', margin: '0 auto 1.5rem', fontSize: '0.875rem' }}>
      Загрузите файлы для добавления в эту папку.
    </p>
    <input 
      type="file" 
      ref={fileInputRef} 
      style={{ display: 'none' }} 
      onChange={handleFileChange}
      accept=".xls,.xlsx,.csv"
    />
    <button 
      className="btn-primary" 
      style={{ margin: '0 auto', fontSize: '0.875rem', padding: '0.5rem 1rem' }}
      onClick={() => fileInputRef.current?.click()}
    >
      Выбрать на компьютере
    </button>
  </div>
  );
};

const FileListItem = ({ file, onRemove }: { file: { name: string, size: string, status: string }, onRemove: () => void }) => (
  <div className="card" style={{ padding: '1rem', display: 'flex', alignItems: 'center', gap: '1rem', transition: 'all 0.2s', borderRadius: '16px' }}>
    <div style={{
      width: '40px',
      height: '40px',
      borderRadius: '10px',
      backgroundColor: 'var(--bg-base)',
      color: 'var(--brand)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }}>
      <FileText size={20} />
    </div>
    
    <div style={{ flex: 1 }}>
      <div className="flex items-center gap-2">
        <span style={{ fontWeight: 700, fontSize: '0.875rem' }}>{file.name}</span>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>{file.size}</span>
      </div>
      <div className="flex items-center gap-3 mt-1">
        <div style={{ height: '4px', backgroundColor: 'var(--bg-base)', borderRadius: '100px', flex: 1, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: '100%', backgroundColor: 'var(--brand)', borderRadius: '100px' }} />
        </div>
        <span style={{ fontSize: '0.625rem', fontWeight: 800, color: 'var(--brand)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <CheckCircle2 size={12} /> Готов
        </span>
      </div>
    </div>

    <button 
      onClick={onRemove}
      style={{
        padding: '0.5rem',
        color: 'var(--text-tertiary)',
        borderRadius: '8px',
        transition: 'all 0.2s'
      }}
      className="hover:bg-rose-50 hover:text-rose-500"
    >
      <Trash2 size={18} />
    </button>
  </div>
);

export const StoragePage: React.FC = () => {
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);
  
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  
  const [files, setFiles] = useState<any[]>([]);

  useEffect(() => {
    if (selectedFolder) {
      fetchHistory();
    }
  }, [selectedFolder]);

  const fetchHistory = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/scheduler/import/history');
      if (res.ok) {
        const data = await res.json();
        // In a real app we'd filter by selectedFolder type
        const mapped = data.map((b: any) => ({
          id: b.id,
          name: b.filename,
          size: b.file_type,
          status: 'ready',
          date: b.created_date
        }));
        setFiles(mapped);
      }
    } catch(err) {
      console.error(err);
    }
  };

  const uploadFile = async (file: File) => {
    setIsUploading(true);
    setError(null);
    setSuccessMsg(null);
    const formData = new FormData();
    formData.append('file', file);
    
    const isTeacherImport = selectedFolder === 'Доступность преподавателей';
    const endpoint = isTeacherImport 
        ? 'http://localhost:8000/api/v1/scheduler/teachers/import'
        : 'http://localhost:8000/api/v1/scheduler/import/streams';

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Upload failed');
      }
      const data = await res.json();
      
      if (isTeacherImport) {
          setSuccessMsg(`Успешно! Обновлено преподавателей: ${data.updated_teachers}`);
      } else {
          setSuccessMsg(`Успешно загружено! Добавлено потоков: ${data.streams_added}, групп: ${data.groups_added}`);
          await fetchHistory();
      }
    } catch(err: any) {
      setError(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDrop = (uploadedFiles: FileList) => {
    if (uploadedFiles.length > 0) {
      uploadFile(uploadedFiles[0]);
    }
  };

  const removeFile = async (index: number) => {
    const file = files[index];
    if (file.id > 0) {
      try {
        const res = await fetch(`http://localhost:8000/api/v1/scheduler/import/history/${file.id}`, { method: 'DELETE' });
        if (res.ok) {
           setSuccessMsg('Файл и связанные данные успешно удалены.');
           await fetchHistory();
        }
      } catch(err) { console.error(err); }
    } else {
      setFiles(files.filter((_, i) => i !== index));
    }
  };

  if (!selectedFolder) {
    return (
      <div className="space-y-10">
        <header>
          <h1 className="text-3xl font-bold text-brand">Хранилище файлов</h1>
          <p className="text-text-secondary mt-2">Выберите папку для просмотра и загрузки данных.</p>
        </header>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '2rem' }}>
          <button 
            className="card"
            onClick={() => setSelectedFolder('Учебные планы и потоки')}
            style={{ 
              display: 'flex', 
              flexDirection: 'column', 
              alignItems: 'center', 
              gap: '1rem', 
              padding: '3rem 2rem',
              transition: 'all 0.2s',
              cursor: 'pointer'
            }}
            onMouseOver={(e) => e.currentTarget.style.transform = 'translateY(-4px)'}
            onMouseOut={(e) => e.currentTarget.style.transform = 'translateY(0)'}
          >
            <Folder size={64} color="var(--brand)" strokeWidth={1.5} />
            <h3 style={{ fontSize: '1.125rem', fontWeight: 800 }}>Учебные планы и потоки</h3>
          </button>

          <button 
            className="card"
            onClick={() => setSelectedFolder('Нагрузка и аудитории')}
            style={{ 
              display: 'flex', 
              flexDirection: 'column', 
              alignItems: 'center', 
              gap: '1rem', 
              padding: '3rem 2rem',
              transition: 'all 0.2s',
              cursor: 'pointer'
            }}
            onMouseOver={(e) => e.currentTarget.style.transform = 'translateY(-4px)'}
            onMouseOut={(e) => e.currentTarget.style.transform = 'translateY(0)'}
          >
            <Folder size={64} color="var(--brand)" strokeWidth={1.5} />
            <h3 style={{ fontSize: '1.125rem', fontWeight: 800 }}>Нагрузка и аудитории</h3>
          </button>

          <button 
            className="card"
            onClick={() => setSelectedFolder('Доступность преподавателей')}
            style={{ 
              display: 'flex', 
              flexDirection: 'column', 
              alignItems: 'center', 
              gap: '1rem', 
              padding: '3rem 2rem',
              transition: 'all 0.2s',
              cursor: 'pointer'
            }}
            onMouseOver={(e) => e.currentTarget.style.transform = 'translateY(-4px)'}
            onMouseOut={(e) => e.currentTarget.style.transform = 'translateY(0)'}
          >
            <Folder size={64} color="#f59e0b" strokeWidth={1.5} />
            <h3 style={{ fontSize: '1.125rem', fontWeight: 800 }}>Доступность преподавателей</h3>
          </button>
        </div>
      </div>
    );
  }

  const handleExportTeachers = () => {
    window.open('http://localhost:8000/api/v1/scheduler/teachers/export', '_blank');
  };

  return (
    <div className="space-y-8">
      <header>
        <button 
          onClick={() => setSelectedFolder(null)}
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', marginBottom: '1rem', fontWeight: 600 }}
        >
          <ArrowLeft size={18} /> Назад в хранилище
        </button>
        <h1 className="text-3xl font-bold text-brand" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Folder size={32} /> {selectedFolder}
        </h1>
        
        {error && <div style={{marginTop: '1rem', padding: '1rem', background: '#fee2e2', color: '#b91c1c', borderRadius: '12px'}}>{error}</div>}
        {successMsg && <div style={{marginTop: '1rem', padding: '1rem', background: '#dcfce7', color: '#15803d', borderRadius: '12px'}}>{successMsg}</div>}
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: selectedFolder === 'Доступность преподавателей' ? '1fr' : '1.5fr 1fr', gap: '2.5rem' }}>
        <div className="space-y-6">
          {selectedFolder === 'Доступность преподавателей' && (
            <div className="card" style={{ padding: '2rem', backgroundColor: 'rgba(245, 158, 11, 0.05)', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
                <h3 style={{ fontWeight: 800, marginBottom: '1rem', color: '#b45309' }}>Управление доступностью</h3>
                <p style={{ fontSize: '0.875rem', color: '#92400e', marginBottom: '1.5rem', lineHeight: 1.6 }}>
                    Вы можете выгрузить текущий список преподавателей в Excel, отредактировать их окна доступности и загрузить файл обратно. 
                    Формат: День_Пара (например, 0_1 для Пн 1 пара) или ГГГГ-ММ-ДД_Пара для конкретных дат.
                </p>
                <button 
                    onClick={handleExportTeachers}
                    className="btn-primary" 
                    style={{ backgroundColor: '#f59e0b', boxShadow: '0 4px 12px rgba(245, 158, 11, 0.3)' }}
                >
                    Скачать текущую доступность (Excel)
                </button>
            </div>
          )}
          <DragDropZone 
            onDrop={handleDrop} 
            isDragging={isDragging} 
            setIsDragging={setIsDragging} 
          />
        </div>

        {selectedFolder !== 'Доступность преподавателей' && (
            <div className="space-y-4">
            <h3 style={{ fontSize: '1.125rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                Загруженные файлы
                <span style={{ fontSize: '0.75rem', padding: '0.125rem 0.5rem', backgroundColor: 'var(--bg-base)', borderRadius: '100px', color: 'var(--text-tertiary)' }}>
                {files.length}
                </span>
                {isUploading && <span style={{ fontSize: '0.8rem', color: 'var(--brand)' }}>Загрузка...</span>}
            </h3>
            <div className="space-y-3">
                {files.map((file, idx) => (
                <FileListItem 
                    key={idx} 
                    file={file} 
                    onRemove={() => removeFile(idx)} 
                />
                ))}
                {files.length === 0 && (
                <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-tertiary)', border: '1px dashed var(--border-light)', borderRadius: '24px' }}>
                    Папка пуста
                </div>
                )}
            </div>
            </div>
        )}
      </div>
    </div>
  );
};
