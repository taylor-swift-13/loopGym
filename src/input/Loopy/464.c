// Source: data/benchmarks/sv-benchmarks/loops/sum04-2.c
#define a (2)
#define SIZE 8
void loopy_464(int i) { 
  int sn=0;
  {
  i=1;
  while (i<=SIZE) {
    sn = sn + a;
    i++;
  }
}
  {;
//@ assert(sn==SIZE*a || sn == 0);
}

}
