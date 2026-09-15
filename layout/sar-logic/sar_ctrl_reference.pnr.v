module sar_ctrl_a (c0,
    c1,
    c2,
    c3,
    c4,
    c5,
    c6,
    c7,
    c8,
    c9,
    clk,
    cmp,
    mode,
    drdy,
    rel_n_128n,
    rel_n_128p,
    rel_n_16n,
    rel_n_16p,
    rel_n_1n,
    rel_n_1p,
    rel_n_256n,
    rel_n_256p,
    rel_n_2n,
    rel_n_2p,
    rel_n_32n,
    rel_n_32p,
    rel_n_4n,
    rel_n_4p,
    rel_n_64n,
    rel_n_64p,
    rel_n_8n,
    rel_n_8p,
    samp_tp_n,
    sel_hi_n_128n,
    sel_hi_n_128p,
    sel_hi_n_16n,
    sel_hi_n_16p,
    sel_hi_n_1n,
    sel_hi_n_1p,
    sel_hi_n_256n,
    sel_hi_n_256p,
    sel_hi_n_2n,
    sel_hi_n_2p,
    sel_hi_n_32n,
    sel_hi_n_32p,
    sel_hi_n_4n,
    sel_hi_n_4p,
    sel_hi_n_64n,
    sel_hi_n_64p,
    sel_hi_n_8n,
    sel_hi_n_8p,
    sel_in_n,
    sel_lo_n_128n,
    sel_lo_n_128p,
    sel_lo_n_16n,
    sel_lo_n_16p,
    sel_lo_n_1n,
    sel_lo_n_1p,
    sel_lo_n_256n,
    sel_lo_n_256p,
    sel_lo_n_2n,
    sel_lo_n_2p,
    sel_lo_n_32n,
    sel_lo_n_32p,
    sel_lo_n_4n,
    sel_lo_n_4p,
    sel_lo_n_64n,
    sel_lo_n_64p,
    sel_lo_n_8n,
    sel_lo_n_8p,
    start);
 output c0;
 output c1;
 output c2;
 output c3;
 output c4;
 output c5;
 output c6;
 output c7;
 output c8;
 output c9;
 input clk;
 input cmp;
 input mode;
 output drdy;
 output rel_n_128n;
 output rel_n_128p;
 output rel_n_16n;
 output rel_n_16p;
 output rel_n_1n;
 output rel_n_1p;
 output rel_n_256n;
 output rel_n_256p;
 output rel_n_2n;
 output rel_n_2p;
 output rel_n_32n;
 output rel_n_32p;
 output rel_n_4n;
 output rel_n_4p;
 output rel_n_64n;
 output rel_n_64p;
 output rel_n_8n;
 output rel_n_8p;
 output samp_tp_n;
 output sel_hi_n_128n;
 output sel_hi_n_128p;
 output sel_hi_n_16n;
 output sel_hi_n_16p;
 output sel_hi_n_1n;
 output sel_hi_n_1p;
 output sel_hi_n_256n;
 output sel_hi_n_256p;
 output sel_hi_n_2n;
 output sel_hi_n_2p;
 output sel_hi_n_32n;
 output sel_hi_n_32p;
 output sel_hi_n_4n;
 output sel_hi_n_4p;
 output sel_hi_n_64n;
 output sel_hi_n_64p;
 output sel_hi_n_8n;
 output sel_hi_n_8p;
 output sel_in_n;
 output sel_lo_n_128n;
 output sel_lo_n_128p;
 output sel_lo_n_16n;
 output sel_lo_n_16p;
 output sel_lo_n_1n;
 output sel_lo_n_1p;
 output sel_lo_n_256n;
 output sel_lo_n_256p;
 output sel_lo_n_2n;
 output sel_lo_n_2p;
 output sel_lo_n_32n;
 output sel_lo_n_32p;
 output sel_lo_n_4n;
 output sel_lo_n_4p;
 output sel_lo_n_64n;
 output sel_lo_n_64p;
 output sel_lo_n_8n;
 output sel_lo_n_8p;
 input start;

 wire _000_;
 wire _001_;
 wire _002_;
 wire _003_;
 wire _004_;
 wire _005_;
 wire _006_;
 wire _007_;
 wire _008_;
 wire _010_;
 wire _011_;
 wire _012_;
 wire _013_;
 wire _014_;
 wire _015_;
 wire _016_;
 wire _017_;
 wire _018_;
 wire _019_;
 wire _020_;
 wire _021_;
 wire _022_;
 wire _023_;
 wire _024_;
 wire _025_;
 wire _026_;
 wire _027_;
 wire _028_;
 wire _029_;
 wire _030_;
 wire _031_;
 wire _032_;
 wire _033_;
 wire _034_;
 wire _035_;
 wire _036_;
 wire _037_;
 wire _038_;
 wire _039_;
 wire _040_;
 wire _041_;
 wire _042_;
 wire _043_;
 wire _044_;
 wire _045_;
 wire _046_;
 wire _047_;
 wire _048_;
 wire _049_;
 wire _050_;
 wire _051_;
 wire _052_;
 wire _053_;
 wire _054_;
 wire _055_;
 wire _056_;
 wire _057_;
 wire _058_;
 wire _059_;
 wire _060_;
 wire _061_;
 wire _062_;
 wire _063_;
 wire _064_;
 wire c0_r;
 wire c1_r;
 wire c2_r;
 wire c3_r;
 wire c4_r;
 wire c5_r;
 wire c6_r;
 wire c7_r;
 wire c8_r;
 wire c9_r;
 wire eng1;
 wire eng2;
 wire eng3;
 wire eng4;
 wire eng5;
 wire eng6;
 wire eng7;
 wire eng8;
 wire eng9;
 wire q0;
 wire q1;
 wire q2;
 wire q3;
 wire q4;
 wire q5;
 wire q6;
 wire q7;
 wire q8;
 wire q9;
 wire clknet_0_clk;
 wire clknet_2_0__leaf_clk;
 wire clknet_2_1__leaf_clk;
 wire clknet_2_2__leaf_clk;
 wire clknet_2_3__leaf_clk;
 wire [15:0] _009_;
 wire [15:0] ph;

 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _065_ (.I(eng3),
    .ZN(_030_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _066_ (.I(mode),
    .ZN(_031_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _067_ (.I(ph[2]),
    .ZN(_032_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _068_ (.I(ph[0]),
    .ZN(_033_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _069_ (.I(ph[1]),
    .ZN(_034_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _070_ (.I(ph[3]),
    .ZN(_035_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _071_ (.I(eng4),
    .ZN(_036_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _072_ (.I(eng5),
    .ZN(_037_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _073_ (.I(eng6),
    .ZN(_038_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _074_ (.I(eng7),
    .ZN(_039_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _075_ (.I(eng8),
    .ZN(_040_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _076_ (.I(eng9),
    .ZN(_041_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _077_ (.I(eng2),
    .ZN(_042_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _078_ (.I(ph[12]),
    .ZN(_043_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _079_ (.I(eng1),
    .ZN(_044_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _080_ (.I(ph[13]),
    .ZN(_045_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _081_ (.I(ph[11]),
    .ZN(_046_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _082_ (.I(ph[10]),
    .ZN(_047_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _083_ (.I(ph[9]),
    .ZN(_048_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _084_ (.I(ph[8]),
    .ZN(_049_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _085_ (.I(ph[7]),
    .ZN(_050_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _086_ (.I(ph[6]),
    .ZN(_051_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _087_ (.I(ph[5]),
    .ZN(_052_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _088_ (.I(ph[4]),
    .ZN(_053_));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _089_ (.I(ph[14]),
    .ZN(_054_));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _090_ (.A1(_030_),
    .A2(q3),
    .ZN(sel_lo_n_4p));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 _091_ (.A1(_030_),
    .A2(_031_),
    .A3(q3),
    .ZN(sel_hi_n_4n));
 gf180mcu_fd_sc_mcu7t5v0__nand3_1 _092_ (.A1(_032_),
    .A2(_033_),
    .A3(_034_),
    .ZN(samp_tp_n));
 gf180mcu_fd_sc_mcu7t5v0__or4_1 _093_ (.A1(ph[2]),
    .A2(ph[0]),
    .A3(ph[1]),
    .A4(ph[3]),
    .Z(sel_in_n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _094_ (.A1(eng3),
    .A2(sel_in_n),
    .ZN(rel_n_4p));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _095_ (.A1(eng3),
    .A2(mode),
    .B(sel_in_n),
    .ZN(rel_n_4n));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _096_ (.A1(eng3),
    .A2(q3),
    .Z(sel_hi_n_4p));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _097_ (.A1(q4),
    .A2(eng4),
    .Z(sel_hi_n_8p));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _098_ (.A1(mode),
    .A2(sel_hi_n_8p),
    .Z(sel_lo_n_8n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _099_ (.A1(q4),
    .A2(_036_),
    .ZN(sel_lo_n_8p));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 _100_ (.A1(_031_),
    .A2(q4),
    .A3(_036_),
    .ZN(sel_hi_n_8n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _101_ (.A1(eng4),
    .A2(sel_in_n),
    .ZN(rel_n_8p));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _102_ (.A1(mode),
    .A2(eng4),
    .B(sel_in_n),
    .ZN(rel_n_8n));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _103_ (.A1(q5),
    .A2(eng5),
    .Z(sel_hi_n_16p));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _104_ (.A1(mode),
    .A2(sel_hi_n_16p),
    .Z(sel_lo_n_16n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _105_ (.A1(q5),
    .A2(_037_),
    .ZN(sel_lo_n_16p));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 _106_ (.A1(_031_),
    .A2(q5),
    .A3(_037_),
    .ZN(sel_hi_n_16n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _107_ (.A1(eng5),
    .A2(sel_in_n),
    .ZN(rel_n_16p));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _108_ (.A1(mode),
    .A2(eng5),
    .B(sel_in_n),
    .ZN(rel_n_16n));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _109_ (.A1(q6),
    .A2(eng6),
    .Z(sel_hi_n_32p));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _110_ (.A1(mode),
    .A2(sel_hi_n_32p),
    .Z(sel_lo_n_32n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _111_ (.A1(q6),
    .A2(_038_),
    .ZN(sel_lo_n_32p));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 _112_ (.A1(_031_),
    .A2(q6),
    .A3(_038_),
    .ZN(sel_hi_n_32n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _113_ (.A1(eng6),
    .A2(sel_in_n),
    .ZN(rel_n_32p));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _114_ (.A1(mode),
    .A2(eng6),
    .B(sel_in_n),
    .ZN(rel_n_32n));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _115_ (.A1(q7),
    .A2(eng7),
    .Z(sel_hi_n_64p));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _116_ (.A1(mode),
    .A2(sel_hi_n_64p),
    .Z(sel_lo_n_64n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _117_ (.A1(q7),
    .A2(_039_),
    .ZN(sel_lo_n_64p));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 _118_ (.A1(_031_),
    .A2(q7),
    .A3(_039_),
    .ZN(sel_hi_n_64n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _119_ (.A1(eng7),
    .A2(sel_in_n),
    .ZN(rel_n_64p));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _120_ (.A1(mode),
    .A2(eng7),
    .B(sel_in_n),
    .ZN(rel_n_64n));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _121_ (.A1(q8),
    .A2(eng8),
    .Z(sel_hi_n_128p));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _122_ (.A1(mode),
    .A2(sel_hi_n_128p),
    .Z(sel_lo_n_128n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _123_ (.A1(q8),
    .A2(_040_),
    .ZN(sel_lo_n_128p));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 _124_ (.A1(_031_),
    .A2(q8),
    .A3(_040_),
    .ZN(sel_hi_n_128n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _125_ (.A1(eng8),
    .A2(sel_in_n),
    .ZN(rel_n_128p));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _126_ (.A1(mode),
    .A2(eng8),
    .B(sel_in_n),
    .ZN(rel_n_128n));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _127_ (.A1(mode),
    .A2(sel_hi_n_4p),
    .Z(sel_lo_n_4n));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _128_ (.A1(q9),
    .A2(eng9),
    .Z(sel_hi_n_256p));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _129_ (.A1(mode),
    .A2(sel_hi_n_256p),
    .Z(sel_lo_n_256n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _130_ (.A1(q9),
    .A2(_041_),
    .ZN(sel_lo_n_256p));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 _131_ (.A1(_031_),
    .A2(q9),
    .A3(_041_),
    .ZN(sel_hi_n_256n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _132_ (.A1(eng9),
    .A2(sel_in_n),
    .ZN(rel_n_256p));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _133_ (.A1(mode),
    .A2(eng9),
    .B(sel_in_n),
    .ZN(rel_n_256n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _134_ (.A1(eng2),
    .A2(sel_in_n),
    .ZN(rel_n_2p));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _135_ (.A1(eng2),
    .A2(q2),
    .Z(sel_hi_n_2p));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _136_ (.A1(_043_),
    .A2(_044_),
    .B(ph[13]),
    .ZN(_000_));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _137_ (.A1(_042_),
    .A2(_046_),
    .B(ph[13]),
    .ZN(_001_));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _138_ (.A1(_042_),
    .A2(q2),
    .ZN(sel_lo_n_2p));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _139_ (.A1(_030_),
    .A2(_047_),
    .B(ph[13]),
    .ZN(_002_));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _140_ (.A1(_036_),
    .A2(_048_),
    .B(ph[13]),
    .ZN(_003_));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _141_ (.A1(_037_),
    .A2(_049_),
    .B(ph[13]),
    .ZN(_004_));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _142_ (.A1(_038_),
    .A2(_050_),
    .B(ph[13]),
    .ZN(_005_));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _143_ (.A1(mode),
    .A2(eng2),
    .B(sel_in_n),
    .ZN(rel_n_2n));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _144_ (.A1(_039_),
    .A2(_051_),
    .B(ph[13]),
    .ZN(_006_));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _145_ (.A1(_040_),
    .A2(_052_),
    .B(ph[13]),
    .ZN(_007_));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _146_ (.A1(_041_),
    .A2(_053_),
    .B(ph[13]),
    .ZN(_008_));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 _147_ (.A1(_031_),
    .A2(_042_),
    .A3(q2),
    .ZN(sel_hi_n_2n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _148_ (.A1(_054_),
    .A2(start),
    .ZN(_009_[15]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _149_ (.A1(_045_),
    .A2(start),
    .ZN(_009_[14]));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _150_ (.A1(mode),
    .A2(sel_hi_n_2p),
    .Z(sel_lo_n_2n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _151_ (.A1(_043_),
    .A2(start),
    .ZN(_009_[13]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _152_ (.A1(_046_),
    .A2(start),
    .ZN(_009_[12]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _153_ (.A1(eng1),
    .A2(sel_in_n),
    .ZN(rel_n_1p));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _154_ (.A1(_047_),
    .A2(start),
    .ZN(_009_[11]));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _155_ (.A1(eng1),
    .A2(q1),
    .Z(sel_hi_n_1p));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _156_ (.A1(_048_),
    .A2(start),
    .ZN(_009_[10]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _157_ (.A1(_049_),
    .A2(start),
    .ZN(_009_[9]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _158_ (.A1(_044_),
    .A2(q1),
    .ZN(sel_lo_n_1p));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _159_ (.A1(_050_),
    .A2(start),
    .ZN(_009_[8]));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _160_ (.A1(mode),
    .A2(sel_hi_n_1p),
    .Z(sel_lo_n_1n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _161_ (.A1(_051_),
    .A2(start),
    .ZN(_009_[7]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _162_ (.A1(_052_),
    .A2(start),
    .ZN(_009_[6]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 _163_ (.A1(_031_),
    .A2(_044_),
    .A3(q1),
    .ZN(sel_hi_n_1n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _164_ (.A1(_053_),
    .A2(start),
    .ZN(_009_[5]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _165_ (.A1(_035_),
    .A2(start),
    .ZN(_009_[4]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _166_ (.A1(_032_),
    .A2(start),
    .ZN(_009_[3]));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _167_ (.A1(mode),
    .A2(eng1),
    .B(sel_in_n),
    .ZN(rel_n_1n));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _168_ (.A1(_034_),
    .A2(start),
    .ZN(_009_[2]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _169_ (.A1(_033_),
    .A2(start),
    .ZN(_009_[1]));
 gf180mcu_fd_sc_mcu7t5v0__or2_1 _170_ (.A1(start),
    .A2(ph[15]),
    .Z(_009_[0]));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 _171_ (.I0(c8_r),
    .I1(q8),
    .S(ph[14]),
    .Z(_010_));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 _172_ (.I0(c9_r),
    .I1(q9),
    .S(ph[14]),
    .Z(_011_));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _173_ (.A1(ph[13]),
    .A2(q0),
    .ZN(_055_));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _174_ (.A1(ph[13]),
    .A2(cmp),
    .B(_055_),
    .ZN(_012_));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 _175_ (.I0(c0_r),
    .I1(q0),
    .S(ph[14]),
    .Z(_013_));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _176_ (.A1(q6),
    .A2(ph[7]),
    .ZN(_056_));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _177_ (.A1(ph[7]),
    .A2(cmp),
    .B(_056_),
    .ZN(_014_));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 _178_ (.I0(c1_r),
    .I1(q1),
    .S(ph[14]),
    .Z(_015_));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 _179_ (.I0(c2_r),
    .I1(q2),
    .S(ph[14]),
    .Z(_016_));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _180_ (.A1(q2),
    .A2(ph[11]),
    .ZN(_057_));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _181_ (.A1(ph[11]),
    .A2(cmp),
    .B(_057_),
    .ZN(_017_));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _182_ (.A1(q7),
    .A2(ph[6]),
    .ZN(_058_));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _183_ (.A1(ph[6]),
    .A2(cmp),
    .B(_058_),
    .ZN(_018_));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _184_ (.A1(q5),
    .A2(ph[8]),
    .ZN(_059_));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _185_ (.A1(ph[8]),
    .A2(cmp),
    .B(_059_),
    .ZN(_019_));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _186_ (.A1(ph[12]),
    .A2(q1),
    .ZN(_060_));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _187_ (.A1(ph[12]),
    .A2(cmp),
    .B(_060_),
    .ZN(_020_));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 _188_ (.I0(c3_r),
    .I1(q3),
    .S(ph[14]),
    .Z(_021_));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _189_ (.A1(q8),
    .A2(ph[5]),
    .ZN(_061_));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _190_ (.A1(ph[5]),
    .A2(cmp),
    .B(_061_),
    .ZN(_022_));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 _191_ (.I0(c4_r),
    .I1(q4),
    .S(ph[14]),
    .Z(_023_));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 _192_ (.I0(c5_r),
    .I1(q5),
    .S(ph[14]),
    .Z(_024_));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _193_ (.A1(q4),
    .A2(ph[9]),
    .ZN(_062_));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _194_ (.A1(ph[9]),
    .A2(cmp),
    .B(_062_),
    .ZN(_025_));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _195_ (.A1(q9),
    .A2(ph[4]),
    .ZN(_063_));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _196_ (.A1(ph[4]),
    .A2(cmp),
    .B(_063_),
    .ZN(_026_));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 _197_ (.I0(c6_r),
    .I1(q6),
    .S(ph[14]),
    .Z(_027_));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 _198_ (.I0(c7_r),
    .I1(q7),
    .S(ph[14]),
    .Z(_028_));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 _199_ (.A1(q3),
    .A2(ph[10]),
    .ZN(_064_));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 _200_ (.A1(ph[10]),
    .A2(cmp),
    .B(_064_),
    .ZN(_029_));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _201_ (.D(_020_),
    .CLK(clknet_2_3__leaf_clk),
    .Q(q1));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _202_ (.D(_017_),
    .CLK(clknet_2_0__leaf_clk),
    .Q(q2));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _203_ (.D(_029_),
    .CLK(clknet_2_1__leaf_clk),
    .Q(q3));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _204_ (.D(_025_),
    .CLK(clknet_2_1__leaf_clk),
    .Q(q4));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _205_ (.D(_019_),
    .CLK(clknet_2_2__leaf_clk),
    .Q(q5));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _206_ (.D(_014_),
    .CLK(clknet_2_3__leaf_clk),
    .Q(q6));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _207_ (.D(_018_),
    .CLK(clknet_2_1__leaf_clk),
    .Q(q7));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _208_ (.D(_022_),
    .CLK(clknet_2_1__leaf_clk),
    .Q(q8));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _209_ (.D(_026_),
    .CLK(clknet_2_1__leaf_clk),
    .Q(q9));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _210_ (.D(_012_),
    .CLK(clknet_2_0__leaf_clk),
    .Q(q0));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _211_ (.D(_013_),
    .CLK(clknet_2_0__leaf_clk),
    .Q(c0_r));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _212_ (.D(_015_),
    .CLK(clknet_2_3__leaf_clk),
    .Q(c1_r));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _213_ (.D(_016_),
    .CLK(clknet_2_0__leaf_clk),
    .Q(c2_r));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _214_ (.D(_021_),
    .CLK(clknet_2_0__leaf_clk),
    .Q(c3_r));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _215_ (.D(_023_),
    .CLK(clknet_2_0__leaf_clk),
    .Q(c4_r));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _216_ (.D(_024_),
    .CLK(clknet_2_2__leaf_clk),
    .Q(c5_r));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _217_ (.D(_027_),
    .CLK(clknet_2_2__leaf_clk),
    .Q(c6_r));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _218_ (.D(_028_),
    .CLK(clknet_2_2__leaf_clk),
    .Q(c7_r));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _219_ (.D(_010_),
    .CLK(clknet_2_0__leaf_clk),
    .Q(c8_r));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _220_ (.D(_011_),
    .CLK(clknet_2_0__leaf_clk),
    .Q(c9_r));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _221_ (.D(_008_),
    .CLK(clknet_2_2__leaf_clk),
    .Q(eng9));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _222_ (.D(_007_),
    .CLK(clknet_2_0__leaf_clk),
    .Q(eng8));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _223_ (.D(_006_),
    .CLK(clknet_2_2__leaf_clk),
    .Q(eng7));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _224_ (.D(_005_),
    .CLK(clknet_2_2__leaf_clk),
    .Q(eng6));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _225_ (.D(_004_),
    .CLK(clknet_2_2__leaf_clk),
    .Q(eng5));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _226_ (.D(_003_),
    .CLK(clknet_2_0__leaf_clk),
    .Q(eng4));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _227_ (.D(_002_),
    .CLK(clknet_2_0__leaf_clk),
    .Q(eng3));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _228_ (.D(_001_),
    .CLK(clknet_2_0__leaf_clk),
    .Q(eng2));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _229_ (.D(_000_),
    .CLK(clknet_2_2__leaf_clk),
    .Q(eng1));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _230_ (.D(_009_[0]),
    .CLK(clknet_2_3__leaf_clk),
    .Q(ph[0]));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _231_ (.D(_009_[1]),
    .CLK(clknet_2_3__leaf_clk),
    .Q(ph[1]));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _232_ (.D(_009_[2]),
    .CLK(clknet_2_3__leaf_clk),
    .Q(ph[2]));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _233_ (.D(_009_[3]),
    .CLK(clknet_2_3__leaf_clk),
    .Q(ph[3]));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _234_ (.D(_009_[4]),
    .CLK(clknet_2_3__leaf_clk),
    .Q(ph[4]));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _235_ (.D(_009_[5]),
    .CLK(clknet_2_1__leaf_clk),
    .Q(ph[5]));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _236_ (.D(_009_[6]),
    .CLK(clknet_2_1__leaf_clk),
    .Q(ph[6]));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _237_ (.D(_009_[7]),
    .CLK(clknet_2_3__leaf_clk),
    .Q(ph[7]));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _238_ (.D(_009_[8]),
    .CLK(clknet_2_2__leaf_clk),
    .Q(ph[8]));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _239_ (.D(_009_[9]),
    .CLK(clknet_2_1__leaf_clk),
    .Q(ph[9]));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _240_ (.D(_009_[10]),
    .CLK(clknet_2_1__leaf_clk),
    .Q(ph[10]));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _241_ (.D(_009_[11]),
    .CLK(clknet_2_0__leaf_clk),
    .Q(ph[11]));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _242_ (.D(_009_[12]),
    .CLK(clknet_2_1__leaf_clk),
    .Q(ph[12]));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _243_ (.D(_009_[13]),
    .CLK(clknet_2_2__leaf_clk),
    .Q(ph[13]));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _244_ (.D(_009_[14]),
    .CLK(clknet_2_2__leaf_clk),
    .Q(ph[14]));
 gf180mcu_fd_sc_mcu7t5v0__dffq_1 _245_ (.D(_009_[15]),
    .CLK(clknet_2_1__leaf_clk),
    .Q(ph[15]));
 gf180mcu_fd_sc_mcu7t5v0__buf_4 clkbuf_0_clk (.I(clk),
    .Z(clknet_0_clk));
 gf180mcu_fd_sc_mcu7t5v0__buf_4 clkbuf_2_0__f_clk (.I(clknet_0_clk),
    .Z(clknet_2_0__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__buf_4 clkbuf_2_1__f_clk (.I(clknet_0_clk),
    .Z(clknet_2_1__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__buf_4 clkbuf_2_2__f_clk (.I(clknet_0_clk),
    .Z(clknet_2_2__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__buf_4 clkbuf_2_3__f_clk (.I(clknet_0_clk),
    .Z(clknet_2_3__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_2 clkload0 (.I(clknet_2_1__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 clkload1 (.I(clknet_2_2__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__inv_3 clkload2 (.I(clknet_2_3__leaf_clk));
 assign c0 = c0_r;
 assign c1 = c1_r;
 assign c2 = c2_r;
 assign c3 = c3_r;
 assign c4 = c4_r;
 assign c5 = c5_r;
 assign c6 = c6_r;
 assign c7 = c7_r;
 assign c8 = c8_r;
 assign c9 = c9_r;
 assign drdy = ph[15];
endmodule
