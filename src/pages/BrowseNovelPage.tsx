import { useState } from 'react';
import { Search, ChevronRight, Star, ArrowDown, ChevronLeft, TrendingUp, Compass, List as ListIcon, ThumbsUp } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function BrowseNovelPage() {
  const [activeTab, setActiveTab] = useState<'discover' | 'directory' | 'omnirec'>('discover');

  return (
    <div className="w-full h-full flex flex-col bg-[#fbf9f1] text-[#333] overflow-hidden font-sans">
      {/* Header */}
      <header className="flex items-center justify-between px-8 py-5 bg-[#fbf9f1] sticky top-0 z-20">
        <div className="flex items-center gap-12">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#5c6aff] flex items-center justify-center text-white font-bold text-xl shadow-md">
              N
            </div>
            <span className="font-semibold text-[15px] text-gray-700">
              Powered by <span className="font-bold text-gray-900">BrowseNovel</span>
            </span>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex items-center gap-8 text-[15px] font-medium text-gray-500">
            <button 
              onClick={() => setActiveTab('discover')}
              className={cn(
                "relative py-2 transition-colors hover:text-gray-900",
                activeTab === 'discover' && "text-gray-900 font-bold"
              )}
            >
              Discover
              {activeTab === 'discover' && <div className="absolute bottom-0 left-0 w-full h-[3px] bg-gray-900 rounded-t-md" />}
            </button>
            <button 
              onClick={() => setActiveTab('directory')}
              className={cn(
                "relative py-2 transition-colors hover:text-gray-900",
                activeTab === 'directory' && "text-gray-900 font-bold"
              )}
            >
              Directory
              {activeTab === 'directory' && <div className="absolute bottom-0 left-0 w-full h-[3px] bg-gray-900 rounded-t-md" />}
            </button>
            <button 
              onClick={() => setActiveTab('omnirec')}
              className={cn(
                "relative py-2 transition-colors hover:text-gray-900",
                activeTab === 'omnirec' && "text-gray-900 font-bold"
              )}
            >
              OmniRec
              {activeTab === 'omnirec' && <div className="absolute bottom-0 left-0 w-full h-[3px] bg-gray-900 rounded-t-md" />}
            </button>
          </nav>
        </div>

        {/* Search Bar */}
        <div className="relative w-[300px]">
          <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none">
            <Search className="w-4 h-4 text-gray-400" />
          </div>
          <input 
            type="text" 
            placeholder="Search novels..." 
            className="w-full bg-[#f0ebd8] border-none rounded-full py-2.5 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-[#5c6aff]/50 transition-all placeholder:text-gray-400 font-medium"
          />
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto custom-scrollbar relative">
        {activeTab === 'discover' && <DiscoverTab />}
        {activeTab === 'directory' && <DirectoryTab />}
        {activeTab === 'omnirec' && <OmniRecTab />}
      </main>
    </div>
  );
}

function DiscoverTab() {
  const popularNovels = [
    { title: "Lord of the Mysteries", pts: 9497, cover: "https://cdn.novelupdates.com/images/2018/08/Lord-of-the-Mysteries.jpg" },
    { title: "Warlock of the Magus World", pts: 9350, cover: "https://cdn.novelupdates.com/images/2016/04/Warlock-of-the-Magus-World.jpg" },
    { title: "The Sacred Ruins", pts: 9320, cover: "https://cdn.novelupdates.com/images/2017/02/the-sacred-ruins.jpg" },
    { title: "Circle of Inevitability", pts: 9140, cover: "https://cdn.novelupdates.com/images/2023/03/Circle-of-Inevitability-1677843701.jpg" },
    { title: "Da Feng Da Geng Ren", pts: 9137, cover: "https://cdn.novelupdates.com/images/2020/09/Da-Feng-Da-Geng-Ren.jpg" },
    { title: "My Senior Brother is Too Steady", pts: 9110, cover: "https://cdn.novelupdates.com/images/2020/05/My-Senior-Brother-is-Too-Steady.jpg" },
    { title: "The Founder of Diabolism", pts: 9109, cover: "https://cdn.novelupdates.com/images/2017/12/Grandmaster-of-Demonic-Cultivation-1.jpg" },
    { title: "Reincarnation Paradise", pts: 9107, cover: "https://cdn.novelupdates.com/images/2018/12/Reincarnation-Paradise.jpg" },
    { title: "A Will Eternal", pts: 9096, cover: "https://cdn.novelupdates.com/images/2016/06/A-Will-Eternal.jpg" },
  ];

  return (
    <div className="max-w-[1200px] mx-auto px-8 py-8 space-y-16 pb-24">
      {/* Hero Carousel Concept */}
      <div className="relative w-full h-[360px] flex items-center justify-center gap-6">
        <button className="absolute left-10 z-10 w-10 h-10 rounded-full bg-black/40 flex items-center justify-center text-white backdrop-blur-sm hover:bg-black/60 transition-colors">
          <ChevronLeft className="w-5 h-5" />
        </button>
        
        {/* Left Card (Dimmed) */}
        <div className="w-[280px] h-[280px] rounded-2xl bg-gray-300 opacity-60 overflow-hidden relative grayscale-[30%]">
           <img src="https://cdn.novelupdates.com/images/2021/04/Magic-School-Wizard.jpg" className="w-full h-full object-cover" />
           <div className="absolute inset-0 bg-black/20" />
        </div>

        {/* Center Card */}
        <div className="w-[600px] h-[360px] rounded-2xl bg-[#0a0a0c] shadow-2xl overflow-hidden relative flex">
          <div className="w-3/5 p-8 flex flex-col justify-center z-10">
            <p className="text-gray-400 text-xs mb-2">深夜书屋</p>
            <h1 className="text-3xl font-bold text-white mb-2">Midnight Bookstore</h1>
            <p className="text-gray-400 text-sm mb-4 flex items-center gap-2">
              <span className="opacity-70">✍ Pure Little Dragon</span>
            </p>
            <div className="flex gap-3 mb-6">
               <div className="bg-blue-500/20 text-blue-400 px-3 py-1 rounded-md text-xs font-bold flex items-center gap-1 border border-blue-500/30">
                 <ArrowDown className="w-3 h-3" /> 8284 pts
               </div>
               <div className="bg-orange-500/20 text-orange-400 px-3 py-1 rounded-md text-xs font-bold flex items-center gap-1 border border-orange-500/30">
                 <Star className="w-3 h-3 fill-orange-400" /> 8.47 (44)
               </div>
            </div>
            <p className="text-gray-300 text-xs leading-relaxed line-clamp-3 mb-6">
              A bookstore that only opens its doors in the dead of night. You are welcome to visit.
            </p>
            <div className="flex gap-2">
              <span className="px-3 py-1 rounded-full bg-indigo-500/20 text-indigo-300 text-[10px] font-bold border border-indigo-500/30">Mystery</span>
              <span className="px-3 py-1 rounded-full bg-purple-500/20 text-purple-300 text-[10px] font-bold border border-purple-500/30">Male Protagonist</span>
            </div>
          </div>
          <div className="absolute right-0 top-0 w-2/5 h-full overflow-hidden mask-image-gradient">
            <img src="https://cdn.novelupdates.com/images/2018/10/Midnight-Bookstore.jpg" className="w-full h-full object-cover object-left opacity-80" />
            <div className="absolute inset-0 bg-gradient-to-r from-[#0a0a0c] via-transparent to-transparent" />
          </div>
        </div>

        {/* Right Card (Dimmed) */}
        <div className="w-[280px] h-[280px] rounded-2xl bg-gray-300 opacity-60 overflow-hidden relative grayscale-[30%]">
           <img src="https://cdn.novelupdates.com/images/2017/04/Way-of-the-Devil.jpg" className="w-full h-full object-cover" />
           <div className="absolute inset-0 bg-black/20" />
        </div>

        <button className="absolute right-10 z-10 w-10 h-10 rounded-full bg-black/40 flex items-center justify-center text-white backdrop-blur-sm hover:bg-black/60 transition-colors">
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>

      <div className="flex justify-center gap-2">
        <div className="w-2 h-2 rounded-full bg-[#8c7a6b]" />
        <div className="w-2 h-2 rounded-full bg-gray-300" />
        <div className="w-2 h-2 rounded-full bg-gray-300" />
        <div className="w-2 h-2 rounded-full bg-gray-300" />
      </div>

      {/* Most Popular */}
      <section>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-[17px] font-bold text-gray-800 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-[#8c7a6b]" /> Most Popular
          </h2>
          <button className="text-[13px] font-semibold text-gray-500 flex items-center gap-1 hover:text-gray-900 transition-colors">
            See more <ChevronRight className="w-4 h-4" />
          </button>
        </div>
        <div className="flex gap-4 overflow-x-auto pb-4 custom-scrollbar">
          {popularNovels.map((novel, i) => (
            <NovelCard key={i} novel={novel} rank={i + 1} />
          ))}
        </div>
      </section>
    </div>
  );
}

function DirectoryTab() {
  return (
    <div className="max-w-[1200px] mx-auto px-8 py-8 flex gap-8">
      {/* Search Results Area */}
      <div className="flex-1 space-y-6">
        <div className="relative">
          <Search className="absolute left-4 top-3.5 w-5 h-5 text-gray-400" />
          <input 
            type="text" 
            placeholder="Search by title or author..." 
            className="w-full bg-[#fbf9f1] border border-gray-200 shadow-sm rounded-xl py-3 pl-12 pr-4 text-[15px] focus:outline-none focus:ring-2 focus:ring-[#5c6aff]/30 transition-all font-medium"
          />
        </div>
        
        <div className="flex items-center justify-between text-xs font-semibold text-gray-400 mb-2">
          <span>1,000 results found in 8ms</span>
          <div className="flex items-center gap-2">
            <ListIcon className="w-4 h-4" />
            <span>12 <ChevronDownIcon className="w-3 h-3 inline" /></span>
          </div>
        </div>

        {/* Result Item */}
        <div className="bg-[#fcfbf7] border border-gray-100 rounded-2xl p-6 flex gap-6 hover:shadow-md transition-shadow cursor-pointer">
          <div className="w-[140px] shrink-0 aspect-[2/3] rounded-lg overflow-hidden shadow-md">
            <img src="https://cdn.novelupdates.com/images/2018/08/Lord-of-the-Mysteries.jpg" className="w-full h-full object-cover" />
          </div>
          <div className="flex-1">
            <p className="text-xs text-gray-500 mb-1">诡秘之主</p>
            <div className="flex justify-between items-start mb-2">
              <h3 className="text-xl font-extrabold text-gray-900">Lord of the Mysteries</h3>
              <div className="flex gap-2">
                <div className="bg-blue-50 text-blue-600 border border-blue-100 px-2 py-0.5 rounded text-[11px] font-bold flex items-center gap-1">
                  <ArrowDown className="w-3 h-3" /> 9497 pts
                </div>
                <div className="bg-orange-50 text-orange-600 border border-orange-100 px-2 py-0.5 rounded text-[11px] font-bold flex items-center gap-1">
                  <Star className="w-3 h-3 fill-orange-500" /> 9.55 (403)
                </div>
              </div>
            </div>
            <p className="text-[13px] text-gray-500 mb-4 flex items-center gap-1">
              ✍ Cuttlefish That Loves Diving
            </p>
            <div className="flex flex-wrap gap-2 mb-4">
              {['Fantasy', 'Mystery', 'Xianxia / Xuanhuan', 'Male Protagonist', 'Transmigration'].map(tag => (
                <span key={tag} className="px-2.5 py-1 rounded-full bg-purple-50 text-purple-600 text-[10px] font-bold border border-purple-100">{tag}</span>
              ))}
            </div>
            <p className="text-sm text-gray-600 line-clamp-3 leading-relaxed mb-4">
              With the rising tide of steam power and machinery, who can come close to being a Beyonder? Shrouded in the fog of history and darkness, who or what is the lurking evil that murmurs in our ears?
              <br/><br/>
              Waking up to face a string of mysteries, Zhou Mingrui finds himself reincarnated as Klein Moretti in an alternate Victorian-era world...
            </p>
            <button className="text-xs font-bold text-gray-500 hover:text-gray-900 flex items-center gap-1 transition-colors">
              Read More <ChevronDownIcon className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>

      {/* Sidebar Filters */}
      <div className="w-[300px] shrink-0 bg-[#f7f4e8] rounded-2xl p-6 h-max">
         <div className="flex items-center justify-between font-bold text-[15px] mb-6">
           <div className="flex items-center gap-2">
             <ListIcon className="w-4 h-4" /> Sort & Filters
           </div>
           <ChevronDownIcon className="w-4 h-4" />
         </div>
         
         <div className="space-y-6">
           <div>
             <label className="block text-[11px] font-bold text-gray-500 mb-2">Sort by</label>
             <button className="w-full bg-[#fbf9f1] border border-gray-200 rounded-lg px-3 py-2.5 text-sm flex justify-between items-center font-medium">
               ↑↓ Relevance <ChevronDownIcon className="w-4 h-4 text-gray-400" />
             </button>
           </div>
           
           <div>
             <label className="block text-[11px] font-bold text-gray-500 mb-2">Filter by Tags</label>
             <div className="space-y-2 mb-3">
               <div className="flex justify-between text-[13px] text-gray-600"><span>Include</span> <span className="text-gray-400">+</span></div>
               <div className="flex justify-between text-[13px] text-gray-600"><span>Exclude</span> <span className="text-gray-400">+</span></div>
             </div>
             <button className="w-full bg-[#fbf9f1] border border-gray-200 rounded-lg px-3 py-2 text-sm font-semibold flex items-center justify-center gap-2">
                <Compass className="w-4 h-4" /> All Tags
             </button>
           </div>

           <div>
             <label className="block text-[11px] font-bold text-gray-500 mb-4">Filter by Range</label>
             <div className="space-y-5">
               <div>
                 <div className="flex justify-between text-xs font-semibold mb-2">
                   <span>Popularity score</span> <span className="text-gray-400 cursor-pointer hover:underline">Reset</span>
                 </div>
                 <div className="h-1 bg-gray-300 rounded-full relative">
                   <div className="absolute left-0 right-0 h-full bg-[#5c4a3d] rounded-full" />
                   <div className="absolute left-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white border-2 border-[#5c4a3d] rounded-full shadow" />
                   <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white border-2 border-[#5c4a3d] rounded-full shadow" />
                 </div>
                 <div className="flex justify-between text-[10px] text-gray-400 mt-2">
                   <span>MIN<br/>0</span> <span>MAX<br/>10,000</span>
                 </div>
               </div>
               
               <div>
                 <div className="flex justify-between text-xs font-semibold mb-2">
                   <span>Quality score</span> <span className="text-gray-400 cursor-pointer hover:underline">Reset</span>
                 </div>
                 <div className="h-1 bg-gray-300 rounded-full relative">
                   <div className="absolute left-0 right-0 h-full bg-[#5c4a3d] rounded-full" />
                   <div className="absolute left-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white border-2 border-[#5c4a3d] rounded-full shadow" />
                   <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white border-2 border-[#5c4a3d] rounded-full shadow" />
                 </div>
                 <div className="flex justify-between text-[10px] text-gray-400 mt-2">
                   <span>MIN<br/>0.00</span> <span>MAX<br/>10.00</span>
                 </div>
               </div>
             </div>
           </div>
         </div>
      </div>
    </div>
  );
}

function OmniRecTab() {
  return (
    <div className="max-w-[800px] mx-auto px-8 py-8 space-y-8">
       <div className="relative">
          <Search className="absolute left-4 top-3.5 w-5 h-5 text-gray-400" />
          <input 
            type="text" 
            placeholder="Search by novel title..." 
            className="w-full bg-[#fbf9f1] border border-gray-200 shadow-sm rounded-xl py-3 pl-12 pr-4 text-[15px] focus:outline-none focus:ring-2 focus:ring-[#5c6aff]/30 transition-all font-medium"
          />
        </div>

        <div className="bg-[#f7f4e8] rounded-2xl p-6 border border-gray-200/50">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-bold text-[14px] flex items-center gap-2 text-gray-700">
              <BookOpenIcon className="w-4 h-4" /> Your novels <span className="bg-gray-200 px-2 py-0.5 rounded text-[10px]">3</span>
            </h3>
            <button className="text-xs font-semibold text-gray-500 hover:text-gray-800">Replace</button>
          </div>
          
          <div className="space-y-1">
            {[
              { title: "Solo Leveling", cover: "https://cdn.novelupdates.com/images/2018/11/Solo-Leveling-1.jpg" },
              { title: "Omniscient Reader's Viewpoint", cover: "https://cdn.novelupdates.com/images/2018/06/Omniscient-Readers-Viewpoint.jpg" },
              { title: "Reverend Insanity", cover: "https://cdn.novelupdates.com/images/2017/02/Gu-Daoist-Master.jpg" }
            ].map(novel => (
              <div key={novel.title} className="flex items-center justify-between p-2 hover:bg-black/5 rounded-lg transition-colors group">
                <div className="flex items-center gap-3">
                   <img src={novel.cover} className="w-8 h-12 object-cover rounded shadow-sm" />
                   <span className="text-[15px] font-semibold text-gray-800">{novel.title}</span>
                </div>
                <div className="flex items-center gap-3 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button className="text-gray-400 hover:text-green-500"><ThumbsUp className="w-4 h-4" /></button>
                  <button className="text-gray-400 hover:text-red-500"><ThumbsUp className="w-4 h-4 rotate-180" /></button>
                  <button className="text-gray-400 hover:text-gray-700 font-bold px-2">×</button>
                </div>
              </div>
            ))}
          </div>
          <p className="text-[11px] text-gray-400 mt-4">Examples only — hit Replace or search to add novels you've actually read.</p>
        </div>

        <div>
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-bold text-[15px] text-gray-800">Recommended Novels</h3>
            <span className="text-xs font-semibold text-gray-500">20 results</span>
          </div>

          <div className="bg-[#fcfbf7] border border-gray-100 rounded-2xl p-6 flex gap-6 shadow-sm">
            <div className="w-[120px] shrink-0 aspect-[2/3] rounded-lg overflow-hidden shadow-md">
              <img src="https://cdn.novelupdates.com/images/2018/08/Lord-of-the-Mysteries.jpg" className="w-full h-full object-cover" />
            </div>
            <div className="flex-1">
              <p className="text-[11px] text-gray-500 mb-1">诡秘之主</p>
              <div className="flex justify-between items-start mb-2">
                <h3 className="text-lg font-extrabold text-gray-900">Lord of the Mysteries</h3>
                <div className="flex gap-2">
                  <div className="bg-blue-50 text-blue-600 border border-blue-100 px-2 py-0.5 rounded text-[10px] font-bold flex items-center gap-1">
                    <ArrowDown className="w-3 h-3" /> 9497 pts
                  </div>
                  <div className="bg-orange-50 text-orange-600 border border-orange-100 px-2 py-0.5 rounded text-[10px] font-bold flex items-center gap-1">
                    <Star className="w-3 h-3 fill-orange-500" /> 9.55 (403)
                  </div>
                  <button className="text-gray-500 hover:text-gray-900 text-xs font-bold flex items-center gap-1 border border-gray-200 px-2 rounded-md hover:bg-gray-100 transition-colors ml-2">
                    + Add
                  </button>
                </div>
              </div>
              <p className="text-[12px] text-gray-500 mb-3 flex items-center gap-1">
                ✍ Cuttlefish That Loves Diving
              </p>
              <div className="flex flex-wrap gap-1.5 mb-3">
                {['Fantasy', 'Mystery', 'Xianxia / Xuanhuan', 'Male Protagonist'].map(tag => (
                  <span key={tag} className="px-2 py-0.5 rounded-full bg-purple-50 text-purple-600 text-[9px] font-bold border border-purple-100">{tag}</span>
                ))}
              </div>
              <p className="text-[13px] text-gray-600 line-clamp-2 leading-relaxed">
                With the rising tide of steam power and machinery, who can come close to being a Beyonder? Shrouded in the fog of history and darkness, who or what is the lurking evil that murmurs in our ears?
              </p>
            </div>
          </div>
        </div>
    </div>
  );
}

function NovelCard({ novel, rank }: { novel: { title: string, pts: number, cover: string }, rank: number }) {
  return (
    <div className="w-[140px] shrink-0 group cursor-pointer">
      <div className="relative aspect-[2/3] rounded-xl overflow-hidden mb-3 shadow-md group-hover:-translate-y-1 transition-transform">
        <img src={novel.cover} className="w-full h-full object-cover" />
        <div className={cn(
          "absolute top-0 left-0 w-6 h-6 flex items-center justify-center text-[10px] font-black text-white rounded-br-lg shadow-sm",
          rank <= 3 ? "bg-orange-500" : "bg-gray-700/80 backdrop-blur-sm"
        )}>
          {rank}
        </div>
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors" />
      </div>
      <div className="text-center px-1">
        <div className="text-[11px] font-bold text-blue-600 mb-1 flex justify-center items-center gap-0.5">
           <ArrowDown className="w-3 h-3" /> {novel.pts} pts
        </div>
        <h3 className="text-[13px] font-bold text-gray-800 line-clamp-2 leading-tight group-hover:text-[#5c6aff] transition-colors">
          {novel.title}
        </h3>
      </div>
    </div>
  );
}

function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="m6 9 6 6 6-6"/>
    </svg>
  );
}

function BookOpenIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
    </svg>
  );
}
