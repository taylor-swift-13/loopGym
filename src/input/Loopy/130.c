// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/hola/19.c

extern int unknown1();

void loopy_130(int n, int m)
{
   
  
  if (n >= 0 && m >= 0 && m < n) {
  int x=0; 
  int y=m;
  while(x<n) {
    x++;
    if(x>m) y++;
  }
  {;
//@ assert(y==n);
}

  }
}